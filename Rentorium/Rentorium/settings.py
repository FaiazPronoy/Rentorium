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
    return os.environ.get(key, DOTENV.get(key, default))


def env_bool(key, default=False):
    return str(env(key, str(default))).strip().lower() in ('1', 'true', 'yes', 'on')


SECRET_KEY = env('DJANGO_SECRET_KEY', 'dev-only-key-change-me-before-deploying')
DEBUG = env_bool('DJANGO_DEBUG', False)
ALLOWED_HOSTS = [h for h in env('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if h]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

_public_hosts = [h for h in ALLOWED_HOSTS
                 if h not in ('localhost', '127.0.0.1', 'testserver')]
CSRF_TRUSTED_ORIGINS = [f'https://{h}' for h in _public_hosts]

if not DEBUG:
    if SECRET_KEY.startswith('dev-only-key') or len(SECRET_KEY) < 40:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            'Set DJANGO_SECRET_KEY to a long random value before turning DEBUG off.')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', True)
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
    'pages',
    'agents',
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
                'pages.context_processors.site_context',
            ],
            'builtins': ['pages.templatetags.icons'],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {'timeout': 20},
    }
}

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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'static_root'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


def _asset_version():
    stamps = []
    for rel in ('css/app.css', 'js/app.js'):
        f = BASE_DIR / 'static' / rel
        if f.exists():
            stamps.append(int(f.stat().st_mtime))
    return str(max(stamps)) if stamps else '1'


ASSET_VERSION = _asset_version()

PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 20

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

SITE_NAME = 'Rentorium'
SITE_LEGAL_NAME = 'Rentorium'
SITE_TAGLINE = 'Property in Bangladesh, without the guesswork.'
SITE_ADDRESS = 'BRAC University, Merul Badda, Dhaka'
SITE_PHONE = '+880 1700 000 000'
SITE_EMAIL = 'hello@rentorium.test'
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
