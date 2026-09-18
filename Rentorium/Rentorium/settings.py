"""
Django settings for Rentorium.

Secrets are read from the environment, with development friendly defaults, so
nothing sensitive is ever committed. Copy .env.example to .env and fill it in
for anything that has to be real.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


DOTENV = {}
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            DOTENV[_k.strip()] = _v.strip().strip('"').strip("'")


def env(key, default=None):
    """Environment first, then .env, then the default."""
    return os.environ.get(key, DOTENV.get(key, default))


def env_bool(key, default=False):
    return str(env(key, str(default))).strip().lower() in ('1', 'true', 'yes', 'on')


# security
SECRET_KEY = env('DJANGO_SECRET_KEY', 'dev-only-key-change-me-before-deploying')
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = [h for h in env('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if h]

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True

# apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'authentication',
    'property',
    'basic',
    'Agents',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'Rentorium.urls'
WSGI_APPLICATION = 'Rentorium.wsgi.application'
ASGI_APPLICATION = 'Rentorium.asgi.application'

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
                'basic.context_processors.site_context',
            ],
            # the icon set is used on nearly every page, so it is a builtin
            # rather than a load tag repeated in forty templates
            'builtins': ['basic.templatetags.icons'],
        },
    },
]

# database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {'timeout': 20},
    }
}

# auth
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'signin'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# i18n/tz
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# static
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'static_root'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


def _asset_version():
    """
    A stamp appended to the stylesheet and script URLs.

    Without it a browser that has already cached app.css keeps serving the old
    one after an update, which looks exactly like "the change did not work".
    Taking the newest modification time means it changes by itself whenever
    either file is edited, and stays stable otherwise.
    """
    stamps = []
    for rel in ('css/app.css', 'js/app.js'):
        f = BASE_DIR / 'static' / rel
        if f.exists():
            stamps.append(int(f.stat().st_mtime))
    return str(max(stamps)) if stamps else '1'


ASSET_VERSION = _asset_version()

# Ownership papers live here, deliberately outside MEDIA_ROOT, so no web
# server ever maps a URL to them. See property/storage.py.
PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024      # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024     # 15 MB
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# email
# With no SMTP settings configured, mail is printed to the console, which is
# what you want while marking or developing.
if env('EMAIL_HOST_USER'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(env('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    EMAIL_HOST_USER = 'no-reply@rentorium.local'

DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
SUPPORT_EMAIL = env('SUPPORT_EMAIL', EMAIL_HOST_USER)

# app config
SITE_NAME = 'Rentorium'
SITE_LEGAL_NAME = 'Rentorium Technologies Limited'
SITE_TAGLINE = 'Property in Bangladesh, without the guesswork.'
SITE_ADDRESS = 'Level 7, 12 North Avenue, Gulshan 2, Dhaka 1212'
SITE_PHONE = '+880 9612 000 200'
SITE_EMAIL = 'hello@rentorium.com.bd'
SITE_HOURS = 'Saturday to Thursday, 9am to 7pm'
CURRENCY_SIGN = '৳'
PROPERTIES_PER_PAGE = 9
MAX_IMAGES_PER_PROPERTY = 8
MAX_COMPARE = 4

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}
