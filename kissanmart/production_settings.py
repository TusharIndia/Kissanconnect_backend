import os
from .settings import *  # noqa: F401,F403 - import base settings

# Override base settings with production-safe defaults read from environment
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('1', 'true', 'yes')

# SECRET_KEY must be provided in environment in production
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', SECRET_KEY)

# Allowed hosts should be provided via env, comma-separated
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',') if os.getenv('DJANGO_ALLOWED_HOSTS') else ['localhost']

# Use dj-database-url if DATABASE_URL provided, else keep existing sqlite config
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    try:
        import dj_database_url
        DATABASES['default'] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    except Exception:
        # If dj-database-url missing or parse error, keep default
        pass

# Static files served with WhiteNoise
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')  # after SecurityMiddleware

# Static files settings for WhiteNoise
STATIC_ROOT = os.getenv('STATIC_ROOT', str(Path(BASE_DIR) / 'staticfiles'))
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', 'True').lower() in ('1', 'true', 'yes')
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '3600'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True').lower() in ('1', 'true', 'yes')
SECURE_HSTS_PRELOAD = os.getenv('DJANGO_SECURE_HSTS_PRELOAD', 'True').lower() in ('1', 'true', 'yes')

# Read additional secrets (social auth) from environment
GOOGLE_OAUTH2_CLIENT_ID = os.getenv('GOOGLE_OAUTH2_CLIENT_ID', GOOGLE_OAUTH2_CLIENT_ID)
GOOGLE_OAUTH2_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH2_CLIENT_SECRET', GOOGLE_OAUTH2_CLIENT_SECRET)
FACEBOOK_APP_ID = os.getenv('FACEBOOK_APP_ID', FACEBOOK_APP_ID)
FACEBOOK_APP_SECRET = os.getenv('FACEBOOK_APP_SECRET', FACEBOOK_APP_SECRET)

# On Vercel, static files are typically built by frontend; but keep static config for collectstatic
