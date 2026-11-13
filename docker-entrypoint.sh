#!/bin/sh
set -e

# docker-compose (local) sets RUN_MIGRATIONS=1. Elsewhere, run migrations once
# per deploy (e.g. the Procfile release step) instead.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
