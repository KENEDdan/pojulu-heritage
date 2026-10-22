FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# postgresql-client provides pg_dump for scripts/backup_db.py (cron service).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl postgresql-client \
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
    && mkdir -p /app/media \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn pojulu_heritage.wsgi:application --bind 0.0.0.0:${PORT:-8000} --worker-class gthread --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-120} --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile -"]
