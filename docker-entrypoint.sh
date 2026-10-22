#!/bin/sh
set -e

# docker-compose (local) sets RUN_MIGRATIONS=1. On Railway, migrations run as
# the preDeployCommand in railway.toml instead.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
