"""Phase 8: logging, Sentry wiring, health check, backups, media integrity."""
import datetime as dt
import io
import json
import logging
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import backup_db  # noqa: E402


# ── backups ──────────────────────────────────────────────────────────────────

def test_pg_env_from_url_and_password_never_in_args():
    env = backup_db.pg_env_from_url('postgresql://phf%40user:s3cr%2Fet@db.internal:6543/phf?sslmode=require')
    assert env == {'PGHOST': 'db.internal', 'PGPORT': '6543', 'PGUSER': 'phf@user', 'PGPASSWORD': 's3cr/et',
                   'PGDATABASE': 'phf', 'PGSSLMODE': 'require'}
    args = backup_db.pg_dump_args(env)
    assert '--format=custom' in args and not any('s3cr' in a for a in args)


def test_rejects_non_postgres_url():
    with pytest.raises(SystemExit):
        backup_db.pg_env_from_url('mysql://u:p@h/db')


def _obj(key, days_ago, now):
    return {'Key': key, 'LastModified': now - dt.timedelta(days=days_ago)}


def test_prune_selects_only_old_backups_and_keeps_minimum():
    now = dt.datetime(2026, 10, 22, tzinfo=dt.timezone.utc)
    objs = [_obj(f'b{d}.dump', d, now) for d in range(0, 60, 5)]   # 12 backups, 0..55 days old
    expired = backup_db.select_expired(objs, now, retention_days=30, keep_min=7)
    assert set(expired) == {'b35.dump', 'b40.dump', 'b45.dump', 'b50.dump', 'b55.dump'}
    # Only old backups exist (e.g. cron was broken for months): keep the newest 7 anyway.
    stale = [_obj(f's{d}.dump', d, now) for d in range(40, 50)]
    assert len(backup_db.select_expired(stale, now, 30, 7)) == 3
    # The backup just uploaded is never pruned.
    assert backup_db.select_expired([_obj('new.dump', 99, now)], now, 30, 0, protect={'new.dump'}) == []


def test_backup_fails_loudly_on_bad_dump(tmp_path, monkeypatch):
    monkeypatch.setenv('PG_DUMP', f'"{sys.executable}" -c "print(1)"')
    with pytest.raises(SystemExit, match='invalid'):
        backup_db.run_dump(tmp_path / 'x.dump', backup_db.pg_env_from_url('postgresql://u:p@h/db'))


# ── media integrity ──────────────────────────────────────────────────────────

def test_check_media_integrity_reports_missing_files(world):
    p = world['person']
    p.photo = SimpleUploadedFile('a.jpg', _jpeg())
    p.save()
    out = io.StringIO()
    call_command('check_media_integrity', stdout=out)
    assert '0 missing' in out.getvalue()
    p.photo.storage.delete(p.photo.name)
    out = io.StringIO()
    call_command('check_media_integrity', stdout=out)
    assert f'MISSING  genealogy.Person.photo pk={p.pk}' in out.getvalue()
    with pytest.raises(CommandError):
        call_command('check_media_integrity', '--fail', stdout=io.StringIO())


def _jpeg():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (10, 10)).save(buf, 'JPEG')
    return buf.getvalue()


# ── health check ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_healthz_is_exempt_from_ssl_redirect_and_reveals_nothing(client, settings):
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = [r'^healthz/?$']
    r = client.get('/healthz')
    assert r.status_code == 200
    assert set(r.json()) == {'status', 'database'}


@pytest.mark.django_db
def test_healthz_reports_db_failure(client, monkeypatch):
    from django.db import connection

    def boom(*a, **k):
        raise RuntimeError('db down: password=hunter2')
    monkeypatch.setattr(connection, 'cursor', boom)
    r = client.get('/healthz')
    assert r.status_code == 503
    assert 'hunter2' not in r.content.decode()


# ── logging ──────────────────────────────────────────────────────────────────

def test_failed_login_is_logged_without_password(client, staff_factory, caplog):
    staff_factory('clan_admin')
    with caplog.at_level(logging.WARNING, logger='phf.security'):
        client.post(reverse('dashboard:login'), {'username': 'clan_admin', 'password': 'Wrong-Pass-123'})
    records = [r for r in caplog.records if getattr(r, 'event', '') == 'login_failed']
    assert records and records[0].username == 'clan_admin'
    assert 'Wrong-Pass-123' not in caplog.text


def test_permission_denial_and_trash_are_logged(client, world, staff_factory, superadmin, caplog):
    with caplog.at_level(logging.INFO, logger='phf.security'):
        client.force_login(staff_factory('clan_admin'))
        client.get(reverse('dashboard:genealogy_dashboard'))
        client.force_login(superadmin)
        client.post(reverse('dashboard:person_delete', args=[world['person'].pk]))
    assert 'Permission denied' in caplog.text and 'Moved to Trash' in caplog.text


def test_json_formatter_outputs_single_line_json():
    from apps.core.logging import JsonFormatter
    rec = logging.makeLogRecord({'name': 'phf.security', 'levelname': 'WARNING', 'msg': 'x %s', 'args': ('y',),
                                 'event': 'login_failed', 'username': 'bob'})
    line = JsonFormatter().format(rec)
    data = json.loads(line)
    assert '\n' not in line and data['msg'] == 'x y' and data['event'] == 'login_failed' and data['username'] == 'bob'


# ── Sentry ───────────────────────────────────────────────────────────────────

def _sentry_probe(**env_extra):
    env = {k: v for k, v in os.environ.items() if k != 'SENTRY_DSN'}
    env.update({'DEBUG': 'False', 'SECRET_KEY': secrets.token_urlsafe(50), 'ALLOWED_HOSTS': 'x.org', **env_extra})
    probe = ("import sentry_sdk; c = sentry_sdk.get_client(); "
             "print(c.is_active(), c.options.get('send_default_pii'), c.options.get('traces_sample_rate'), "
             "c.options.get('environment'), c.options.get('max_request_body_size'))")
    return subprocess.run([sys.executable, 'manage.py', 'shell', '--no-imports', '-c', probe], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


def test_sentry_inactive_without_dsn():
    r = _sentry_probe()
    assert r.returncode == 0, r.stderr
    assert r.stdout.split()[0] == 'False'


def test_sentry_configured_without_pii():
    r = _sentry_probe(SENTRY_DSN='https://public@o0.ingest.sentry.io/0', SENTRY_ENVIRONMENT='staging')
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ['True', 'False', '0.1', 'staging', 'never']
