# Restoring a PHF database backup

Backups are written by `scripts/backup_db.py` in PostgreSQL **custom format**
(`pg_dump --format=custom --compress=9 --no-owner --no-privileges`) and stored at
`s3://<BACKUP_BUCKET_NAME>/db-backups/<yyyy>/<mm>/<dd>/phf-<timestamp>.dump`.

> **Never restore over the live production database to "test" a backup.**
> Always restore into a new, empty database first, check it, then switch.

These steps were tested on 2026-10-22 against the local docker-compose
Postgres 16 container (dump → restore into a scratch DB → table and row counts
compared with the source: identical).

## 0. Prerequisites

- `pg_restore` / `psql` **of the same or newer major version** than the server
  (the project Dockerfile installs the PGDG client, so a shell inside the
  app container has them).
- The bucket credentials (`AWS_*` variables) to download the file.

## 1. Download the backup

With the AWS CLI (works for R2/B2 with `--endpoint-url`):

```bash
aws s3 ls  s3://$BACKUP_BUCKET_NAME/db-backups/ --recursive --endpoint-url $AWS_S3_ENDPOINT_URL | tail
aws s3 cp  s3://$BACKUP_BUCKET_NAME/db-backups/2026/10/22/phf-20261022T020000Z.dump ./phf.dump \
           --endpoint-url $AWS_S3_ENDPOINT_URL
```

Or from the Cloudflare/Backblaze web console.

Sanity-check the file. The first five bytes must be `PGDMP`, and `pg_restore` must be able to list it:

```bash
head -c 5 phf.dump; echo
pg_restore --list phf.dump | head
```

## 2. Restore into a NEW database

### Local (docker-compose), PowerShell

```powershell
docker exec pojulu_heritage_db psql -U postgres -d postgres -c "CREATE DATABASE phf_restore"
Get-Content .\phf.dump -AsByteStream -Raw | docker exec -i pojulu_heritage_db pg_restore -U postgres --no-owner --no-privileges --exit-on-error -d phf_restore
```

(Git Bash: `docker exec -i pojulu_heritage_db pg_restore -U postgres --no-owner --no-privileges --exit-on-error -d phf_restore < phf.dump`)

### Hosted Postgres

1. **Create a new, empty database** on the same host (e.g. `phf_restore`). Do not reuse the live one.
2. Copy its connection URL, then from any machine with `pg_restore`:

```bash
pg_restore --no-owner --no-privileges --exit-on-error --jobs=4 \
           --dbname="$RESTORE_DATABASE_URL" phf.dump
```

## 3. Verify the restored database

```bash
psql "$RESTORE_DATABASE_URL" -c "select count(*) from genealogy_person" \
                             -c "select count(*) from clans_clan" \
                             -c "select max(applied) from django_migrations"
```

Point a local checkout at it and check that Django agrees the schema is complete:

```powershell
$env:DATABASE_URL = "<restore database url>"
py manage.py migrate --check      # exits 0 when no migrations are pending
py manage.py check_media_integrity
Remove-Item Env:DATABASE_URL
```

## 4. Switch production to the restored database

1. Stop the web app (or put it in maintenance) so nothing writes to the old database.
2. Change the app's `DATABASE_URL` to the restored database.
3. Run `python manage.py migrate --noinput` (applies any migrations newer than the backup), then start the app.
4. Check `/healthz`, log in to `/dashboard/`, and spot-check recent records.
5. Keep the old database for at least a week before deleting it.

## 5. Media files

Database backups do **not** include uploaded files. Those live in the R2/B2
buckets. Turn on object versioning or bucket replication there for media
recovery. After a restore, `py manage.py check_media_integrity` lists any
records whose files are missing.
