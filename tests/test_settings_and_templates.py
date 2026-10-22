"""Phase 0/1: deploy settings, admin mounting, template link integrity."""
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.urls import get_resolver

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = list((ROOT / 'templates').rglob('*.html'))


def _prod_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ('DEBUG', 'SECRET_KEY')}
    env.update({
        'DEBUG': 'False',
        'SECRET_KEY': secrets.token_urlsafe(64),
        'ALLOWED_HOSTS': 'phf.example.org',
        'CSRF_TRUSTED_ORIGINS': 'https://phf.example.org,https://*.up.railway.app',
    })
    env.update(extra)
    return env


def _manage(*args, env):
    return subprocess.run([sys.executable, 'manage.py', *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=180)


def test_check_deploy_has_zero_warnings():
    r = _manage('check', '--deploy', '--fail-level', 'WARNING', env=_prod_env())
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'no issues' in r.stdout


def test_missing_secret_key_is_fatal_in_production():
    env = _prod_env()
    env['SECRET_KEY'] = ''
    r = _manage('check', env=env)
    assert r.returncode != 0
    assert 'SECRET_KEY must be set' in r.stderr


def test_django_admin_mounts_only_when_enabled():
    probe = ("from django.urls import reverse;"
             "print(reverse('admin:index'))")
    off = _manage('shell', '--no-imports', '-c', probe, env=_prod_env())
    assert off.returncode != 0 and 'NoReverseMatch' in off.stderr
    on = _manage('shell', '--no-imports', '-c', probe, env=_prod_env(ENABLE_DJANGO_ADMIN='True', ADMIN_URL_PREFIX='hidden-door/'))
    assert on.returncode == 0, on.stderr
    assert on.stdout.strip() == '/hidden-door/'


@pytest.mark.django_db
def test_admin_url_is_404_by_default(client):
    assert client.get('/admin/').status_code == 404


@pytest.mark.django_db
def test_healthz_reports_ok_without_details(client):
    r = client.get('/healthz')
    assert r.status_code == 200
    assert r.json() == {'status': 'ok', 'database': 'ok'}


def test_no_template_links_to_django_admin():
    offenders = [str(t) for t in TEMPLATES
                 if re.search(r"""(href|action)\s*=\s*["'][^"']*/admin/|\{%\s*url\s+['"]admin:""", t.read_text(encoding='utf-8'))]
    assert offenders == []


def test_every_template_url_name_resolves():
    names = set()

    def walk(resolver, ns=''):
        for p in resolver.url_patterns:
            if hasattr(p, 'url_patterns'):
                walk(p, ns + (p.namespace + ':' if p.namespace else ''))
            elif p.name:
                names.add(ns + p.name)
    walk(get_resolver())
    missing = []
    for t in TEMPLATES:
        for m in re.finditer(r"""\{%\s*url\s+['"]([^'"]+)['"]""", t.read_text(encoding='utf-8')):
            if m.group(1) not in names:
                missing.append(f'{t.name}: {m.group(1)}')
    assert missing == []
