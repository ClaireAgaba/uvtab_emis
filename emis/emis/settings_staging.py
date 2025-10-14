from .settings import *  # noqa
import os

# Staging/Training flags
DEBUG = True
IS_STAGING = True
SITE_NAME = os.getenv('SITE_NAME', 'EMIS Training')

# Safety: isolate cookies so training sessions never collide with live
SESSION_COOKIE_NAME = 'emis_staging_sessionid'
CSRF_COOKIE_NAME = 'emis_staging_csrftoken'

# Emails: log to console in training
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Database: reuse Postgres if POSTGRES_* are provided, otherwise use a separate sqlite file
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default']['NAME'] = BASE_DIR / 'db_staging.sqlite3'

# Allow all hosts by default for staging unless overridden
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',') if isinstance(ALLOWED_HOSTS, list) is False else ALLOWED_HOSTS
