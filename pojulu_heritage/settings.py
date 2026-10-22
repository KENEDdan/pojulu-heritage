"""
Pojulu Heritage Foundation settings.

Every environment-specific value comes from environment variables (or a local
.env file via python-decouple). Production behaviour is switched on by
DEBUG=False plus the variables documented in .env.example and docs/HARDENING.md
— never by editing this file.
"""
from pathlib import Path

import dj_database_url
from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ── CORE ──────────────────────────────────────────────────────────────────────

DEBUG = config('DEBUG', default=False, cast=bool)

SECRET_KEY = config('SECRET_KEY', default='')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG is False.')
    SECRET_KEY = 'django-insecure-local-development-only-not-for-production'

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost,http://127.0.0.1', cast=Csv())

# Railway injects RAILWAY_PUBLIC_DOMAIN (e.g. phf-production.up.railway.app);
# trust it automatically so a fresh service works without extra variables.
RAILWAY_PUBLIC_DOMAIN = config('RAILWAY_PUBLIC_DOMAIN', default='')
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_PUBLIC_DOMAIN}')
# Railway's deploy health check calls the container with this Host header.
ALLOWED_HOSTS.append('healthcheck.railway.app')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sitemaps',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_filters',
    'mptt',
    'axes',
    'storages',
    'csp',
    'apps.core',
    'apps.clans',
    'apps.genealogy',
    'apps.memorial',
    'apps.achievements',
    'apps.marriages',
    'apps.cultural',
    'apps.elders',
    'apps.submissions',
    'apps.dashboard',
    'apps.news',
    'apps.wills',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.dashboard.middleware.ActiveAccountMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
    # Must be last: turns axes lockouts into the lockout response.
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'pojulu_heritage.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'pojulu_heritage.wsgi.application'

# ── DATABASE ──────────────────────────────────────────────────────────────────
# DATABASE_URL wins (Railway sets it). Otherwise fall back to the local
# docker-compose Postgres on port 5435.

_LOCAL_DB_URL = 'postgresql://{user}:{pw}@{host}:{port}/{name}'.format(
    user=config('DB_USER', default='postgres'),
    pw=config('DB_PASSWORD', default='postgres'),
    host=config('DB_HOST', default='localhost'),
    port=config('DB_PORT', default='5435'),
    name=config('DB_NAME', default='pojulu_heritage'),
)
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default=_LOCAL_DB_URL),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── AUTH ──────────────────────────────────────────────────────────────────────

AUTHENTICATION_BACKENDS = [
    # Must be first: rejects locked-out username+IP pairs before checking passwords.
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Argon2 for new hashes; existing PBKDF2 hashes keep working and are upgraded
# to Argon2 transparently on the user's next successful login.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'dashboard:login'

# Sessions: 1 hour idle timeout (the expiry slides on every request).
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Number of reverse proxies in front of the app that append to
# X-Forwarded-For (Railway's edge = 1). 0 ignores X-Forwarded-For entirely.
# See apps/core/net.py.
TRUSTED_PROXY_COUNT = config('TRUSTED_PROXY_COUNT', default=0 if DEBUG else 1, cast=int)

# ── django-axes: brute-force lockout for /dashboard/login/ and /family/login/
AXES_ENABLED = config('AXES_ENABLED', default=True, cast=bool)
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'lockout.html'
AXES_CLIENT_IP_CALLABLE = 'apps.core.net.client_ip'
AXES_SENSITIVE_PARAMETERS = ['password', 'passphrase']

# Note: wills are encrypted with a passphrase each owner chooses themself
# (see apps.wills.crypto) — deliberately no server-held key here. There is
# nothing to configure and nothing the app can decrypt on anyone's behalf.

# ── DJANGO ADMIN ──────────────────────────────────────────────────────────────
# Staff use /dashboard/. The Django admin is only mounted when explicitly
# enabled, and only superusers may use it (see pojulu_heritage/urls.py).

ENABLE_DJANGO_ADMIN = config('ENABLE_DJANGO_ADMIN', default=False, cast=bool)
ADMIN_URL_PREFIX = config('ADMIN_URL_PREFIX', default='admin/').strip('/') + '/'
ADMIN_SITE_HEADER = 'Pojulu Heritage Foundation'
ADMIN_SITE_TITLE = 'PHF Admin'
ADMIN_INDEX_TITLE = 'Heritage Archive Administration'

# ── I18N ──────────────────────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Juba'
USE_I18N = True
USE_TZ = True

# ── STATIC & MEDIA ────────────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Dev serves straight from STATICFILES_DIRS so CSS edits show instantly;
# production serves the hashed, compressed output of collectstatic.
WHITENOISE_USE_FINDERS = DEBUG

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Request bodies: non-file form data is capped at 10 MB; uploaded files over
# 5 MB are streamed to a temp file instead of held in memory. Per-type file
# size limits live in apps/core/validators.py.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o640

# Private media (profile PDFs, certificates, personal media, interview
# recordings, submission attachments) lives outside MEDIA_ROOT locally and in
# a separate bucket in production. See apps/core/storage.py.
PRIVATE_MEDIA_ROOT = Path(config('PRIVATE_MEDIA_ROOT', default=str(BASE_DIR / 'private_media')))
PRIVATE_MEDIA_URL_EXPIRE = config('PRIVATE_MEDIA_URL_EXPIRE', default=300, cast=int)  # seconds

# S3-compatible object storage (Cloudflare R2 / Backblaze B2). Enabled when
# AWS_STORAGE_BUCKET_NAME is set; otherwise media is stored on local disk.
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_PRIVATE_STORAGE_BUCKET_NAME = config('AWS_PRIVATE_STORAGE_BUCKET_NAME', default='') or AWS_STORAGE_BUCKET_NAME
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_S3_ENDPOINT_URL = config('AWS_S3_ENDPOINT_URL', default='') or None
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='auto')
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
# Public base URL of the *public* bucket (custom domain or r2.dev URL),
# e.g. https://media.example.org. Without it, public files get signed URLs too.
MEDIA_PUBLIC_BASE_URL = config('MEDIA_PUBLIC_BASE_URL', default='').rstrip('/')

USE_S3_MEDIA = bool(AWS_STORAGE_BUCKET_NAME)
if USE_S3_MEDIA:
    if MEDIA_PUBLIC_BASE_URL and AWS_PRIVATE_STORAGE_BUCKET_NAME == AWS_STORAGE_BUCKET_NAME:
        raise ImproperlyConfigured(
            'MEDIA_PUBLIC_BASE_URL makes the public bucket world-readable, so private media needs its '
            'own bucket: set AWS_PRIVATE_STORAGE_BUCKET_NAME to a different, non-public bucket.')
    _public_opts = {'bucket_name': AWS_STORAGE_BUCKET_NAME, 'location': 'media',
                    'object_parameters': {'CacheControl': 'public, max-age=86400'}}
    if MEDIA_PUBLIC_BASE_URL:
        from urllib.parse import urlsplit
        _u = urlsplit(MEDIA_PUBLIC_BASE_URL)
        _public_opts.update({'custom_domain': (_u.netloc + _u.path).rstrip('/'),
                             'url_protocol': f'{_u.scheme}:', 'querystring_auth': False})
    else:
        _public_opts.update({'querystring_auth': True, 'querystring_expire': 6 * 3600})
    _media_storages = {
        'default': {'BACKEND': 'storages.backends.s3.S3Storage', 'OPTIONS': _public_opts},
        'private': {'BACKEND': 'apps.core.storage.PrivateS3Storage',
                    'OPTIONS': {'bucket_name': AWS_PRIVATE_STORAGE_BUCKET_NAME, 'location': 'private',
                                'querystring_auth': True, 'querystring_expire': PRIVATE_MEDIA_URL_EXPIRE}},
    }
else:
    _media_storages = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'private': {'BACKEND': 'apps.core.storage.PrivateFileSystemStorage'},
    }

STORAGES = {
    **_media_storages,
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

# ── SECURITY ──────────────────────────────────────────────────────────────────

# Railway terminates TLS at its edge and forwards X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    # Railway's internal health check is plain HTTP.
    SECURE_REDIRECT_EXEMPT = [r'^healthz/?$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=True, cast=bool)

# ── CACHE ─────────────────────────────────────────────────────────────────────
# Redis when REDIS_URL is set (shared by all gunicorn workers); otherwise a
# per-process in-memory cache. Without Redis, rate limits and cached blocks
# are counted per worker process.
REDIS_URL = config('REDIS_URL', default='')
if REDIS_URL:
    CACHES = {'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'KEY_PREFIX': 'phf',
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient', 'IGNORE_EXCEPTIONS': True},
    }}
    DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'phf'}}

# ── RATE LIMITING (django-ratelimit, per client IP) ───────────────────────────
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=True, cast=bool)
RATELIMIT_VIEW = 'apps.core.views.ratelimited'

# ── CONTENT SECURITY POLICY (django-csp 4.x) ──────────────────────────────────
# Report-only until the inline scripts/styles/handlers listed in
# docs/HARDENING.md are moved to static files; then set CSP_ENFORCE=True.
from csp.constants import NONE, SELF  # noqa: E402

def _csp_media_sources():
    from urllib.parse import urlsplit
    sources = []
    if MEDIA_PUBLIC_BASE_URL:
        u = urlsplit(MEDIA_PUBLIC_BASE_URL)
        sources.append(f'{u.scheme}://{u.netloc}')
    if USE_S3_MEDIA and AWS_S3_ENDPOINT_URL:
        host = urlsplit(AWS_S3_ENDPOINT_URL).netloc
        sources += [f'https://{host}', f'https://*.{host}']
    return sources

_CSP_DIRECTIVES = {
    'default-src': [SELF],
    'script-src': [SELF, 'https://cdn.jsdelivr.net'],
    'style-src': [SELF, 'https://cdn.jsdelivr.net', 'https://fonts.googleapis.com'],
    'font-src': [SELF, 'https://fonts.gstatic.com', 'https://cdn.jsdelivr.net'],
    'img-src': [SELF, 'data:', *_csp_media_sources()],
    'media-src': [SELF, *_csp_media_sources()],
    'frame-src': ['https://www.youtube-nocookie.com', 'https://player.vimeo.com'],
    'connect-src': [SELF],
    'object-src': [NONE],
    'base-uri': [SELF],
    'form-action': [SELF],
    'frame-ancestors': [NONE],
}
# (Not named CSP_*: django-csp 4 treats CSP_-prefixed settings as the old format.)
_csp_report_uri = config('CSP_REPORT_URI', default='')
if _csp_report_uri:
    _CSP_DIRECTIVES['report-uri'] = [_csp_report_uri]
if config('CSP_ENFORCE', default=False, cast=bool):
    CONTENT_SECURITY_POLICY = {'DIRECTIVES': _CSP_DIRECTIVES}
else:
    CONTENT_SECURITY_POLICY_REPORT_ONLY = {'DIRECTIVES': _CSP_DIRECTIVES}

# ── MISC ──────────────────────────────────────────────────────────────────────

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Pojulu Heritage Foundation <noreply@pojuluheritage.org>')

RECORDS_PER_PAGE = 25
