#!/usr/bin/env python
"""Back up the PHF PostgreSQL database to S3-compatible storage.

    python scripts/backup_db.py                 # dump, upload, prune
    python scripts/backup_db.py --local-dir D   # dump into directory D instead of uploading
    python scripts/backup_db.py --dry-run       # dump + upload, but only *report* what would be pruned

What it does
  1. Runs `pg_dump --format=custom` (compressed, restorable with pg_restore)
     against DATABASE_URL. Credentials go to pg_dump via PG* environment
     variables, never on the command line or in the logs.
  2. Verifies the dump (non-empty, PGDMP header).
  3. Uploads it to s3://$BACKUP_BUCKET_NAME/$BACKUP_PREFIX<yyyy>/<mm>/<dd>/phf-<timestamp>.dump
  4. Deletes backups older than BACKUP_RETENTION_DAYS (default 30), but always
     keeps at least BACKUP_KEEP_MIN (default 7) of the newest backups.

Environment
  DATABASE_URL            postgresql://user:pass@host:port/db  (required)
  BACKUP_BUCKET_NAME      bucket (default: AWS_PRIVATE_STORAGE_BUCKET_NAME, then AWS_STORAGE_BUCKET_NAME)
  BACKUP_PREFIX           key prefix (default: "db-backups/")
  BACKUP_RETENTION_DAYS   default 30
  BACKUP_KEEP_MIN         default 7
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_S3_ENDPOINT_URL / AWS_S3_REGION_NAME
  PG_DUMP                 pg_dump command (default "pg_dump"); may be a prefix
                          such as "docker exec -i pojulu_heritage_db pg_dump"

Exit status is non-zero on any failure, so the Railway cron run shows as failed.
See scripts/restore_db.md for restoring.
"""
import argparse
import datetime as dt
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

DUMP_MAGIC = b'PGDMP'


def pg_env_from_url(url):
    """PG* environment variables for libpq tools from a DATABASE_URL."""
    parts = urlsplit(url)
    if parts.scheme not in ('postgres', 'postgresql', 'pgsql'):
        raise SystemExit('DATABASE_URL must be a postgresql:// URL')
    env = {
        'PGHOST': parts.hostname or 'localhost',
        'PGPORT': str(parts.port or 5432),
        'PGUSER': unquote(parts.username or ''),
        'PGPASSWORD': unquote(parts.password or ''),
        'PGDATABASE': unquote(parts.path.lstrip('/')),
    }
    sslmode = parse_qs(parts.query).get('sslmode')
    if sslmode:
        env['PGSSLMODE'] = sslmode[0]
    return env


def pg_dump_args(pg_env):
    # Pass host/port/user/db explicitly too, so prefixes like `docker exec`
    # (which don't forward our environment) still work; the password only
    # ever travels as PGPASSWORD.
    return ['--format=custom', '--compress=9', '--no-owner', '--no-privileges',
            f'--host={pg_env["PGHOST"]}', f'--port={pg_env["PGPORT"]}',
            f'--username={pg_env["PGUSER"]}', f'--dbname={pg_env["PGDATABASE"]}']


def run_dump(out_path, pg_env):
    cmd = shlex.split(os.environ.get('PG_DUMP', 'pg_dump'))
    if cmd[:2] == ['docker', 'exec']:
        cmd = cmd[:2] + ['-e', f'PGPASSWORD={pg_env["PGPASSWORD"]}'] + cmd[2:]
    env = {**os.environ, **pg_env}
    with open(out_path, 'wb') as out:
        proc = subprocess.run(cmd + pg_dump_args(pg_env), stdout=out, stderr=subprocess.PIPE, env=env)
    if proc.returncode != 0:
        msg = proc.stderr.decode(errors='replace').replace(pg_env['PGPASSWORD'] or '\0', '***')
        raise SystemExit(f'pg_dump failed ({proc.returncode}): {msg.strip()}')
    size = out_path.stat().st_size
    with open(out_path, 'rb') as f:
        if size == 0 or f.read(5) != DUMP_MAGIC:
            raise SystemExit('pg_dump produced an empty or invalid file')
    return size


def select_expired(objects, now, retention_days, keep_min, protect=()):
    """Keys to delete: older than the retention window, never one of the
    `keep_min` newest backups, never a protected key."""
    newest_first = sorted(objects, key=lambda o: o['LastModified'], reverse=True)
    cutoff = now - dt.timedelta(days=retention_days)
    expired = []
    for i, obj in enumerate(newest_first):
        if i < keep_min or obj['Key'] in protect:
            continue
        if obj['LastModified'] < cutoff:
            expired.append(obj['Key'])
    return expired


def s3_client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        's3',
        endpoint_url=os.environ.get('AWS_S3_ENDPOINT_URL') or None,
        region_name=os.environ.get('AWS_S3_REGION_NAME') or 'auto',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        config=Config(signature_version='s3v4', retries={'max_attempts': 5, 'mode': 'standard'}),
    )


def list_backups(client, bucket, prefix):
    objs = []
    for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=prefix):
        objs += [o for o in page.get('Contents', []) if o['Key'].endswith('.dump')]
    return objs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--local-dir', help='Write the dump here instead of uploading it.')
    parser.add_argument('--dry-run', action='store_true', help='Report, but do not delete, expired backups.')
    args = parser.parse_args(argv)

    url = os.environ.get('DATABASE_URL')
    if not url:
        raise SystemExit('DATABASE_URL is not set')
    pg_env = pg_env_from_url(url)
    now = dt.datetime.now(dt.timezone.utc)
    name = f'phf-{now:%Y%m%dT%H%M%SZ}.dump'

    if args.local_dir:
        out = Path(args.local_dir) / name
        out.parent.mkdir(parents=True, exist_ok=True)
        size = run_dump(out, pg_env)
        print(f'Backup written: {out} ({size:,} bytes)')
        return 0

    bucket = (os.environ.get('BACKUP_BUCKET_NAME') or os.environ.get('AWS_PRIVATE_STORAGE_BUCKET_NAME')
              or os.environ.get('AWS_STORAGE_BUCKET_NAME'))
    if not bucket:
        raise SystemExit('No bucket: set BACKUP_BUCKET_NAME (or use --local-dir)')
    prefix = os.environ.get('BACKUP_PREFIX', 'db-backups/')
    retention = int(os.environ.get('BACKUP_RETENTION_DAYS', '30'))
    keep_min = int(os.environ.get('BACKUP_KEEP_MIN', '7'))
    key = f'{prefix}{now:%Y/%m/%d}/{name}'

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        size = run_dump(path, pg_env)
        client = s3_client()
        client.upload_file(str(path), bucket, key, ExtraArgs={'ContentType': 'application/octet-stream'})
    head = client.head_object(Bucket=bucket, Key=key)
    if head['ContentLength'] != size:
        raise SystemExit(f'Uploaded size mismatch for {key}')
    print(f'Backup uploaded: s3://{bucket}/{key} ({size:,} bytes)')

    expired = select_expired(list_backups(client, bucket, prefix), now, retention, keep_min, protect={key})
    for old in expired:
        if args.dry_run:
            print(f'Would delete expired backup: {old}')
        else:
            client.delete_object(Bucket=bucket, Key=old)
            print(f'Deleted expired backup: {old}')
    print(f'Done. {len(expired)} expired backup(s) {"found" if args.dry_run else "deleted"}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
