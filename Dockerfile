FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# pg_dump/pg_restore for scripts/backup_db.py (Railway cron service). They
# must be at least the server's major version, so install them from the
# PostgreSQL project's apt repo rather than Debian's older default.
ARG PG_CLIENT_VERSION=17
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl ca-certificates \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-${PG_CLIENT_VERSION} \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

# Hashed + compressed static files are baked into the image. The throwaway
# key only exists for this build step (collectstatic never signs anything).
RUN SECRET_KEY=collectstatic-build-only DEBUG=False python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/media /app/private_media \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn pojulu_heritage.wsgi:application --bind 0.0.0.0:${PORT:-8000} --worker-class gthread --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-120} --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile -"]
