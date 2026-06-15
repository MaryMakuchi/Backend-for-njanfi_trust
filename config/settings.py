from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-njangi-dev-key-change-in-prod')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,10.0.2.2', cast=Csv())
# In development, also allow connections from devices on the local network
# (e.g. a physical phone reaching the dev server via the host's LAN IP).
if DEBUG and ALLOWED_HOSTS != ['*']:
    ALLOWED_HOSTS.append('*')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'accounts',
    'groups',
    'contributions',
    'loans',
    'ledger',
    'notifications',
    'blockchain',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASE_URL = config('DATABASE_URL', default='')
if DATABASE_URL.startswith('postgres'):
    import re
    match = re.match(
        r'postgres://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)/(?P<name>.+)',
        DATABASE_URL,
    )
    if match:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': match.group('name'),
                'USER': match.group('user'),
                'PASSWORD': match.group('password'),
                'HOST': match.group('host'),
                'PORT': match.group('port'),
            }
        }
    else:
        DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S%z',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
if CORS_ALLOWED_ORIGINS:
    CORS_ALLOW_ALL_ORIGINS = False

SPECTACULAR_SETTINGS = {
    'TITLE': 'Njangi Trust API',
    'DESCRIPTION': 'Backend API for the Njangi Trust mobile application',
    'VERSION': '1.0.0',
}

# --- Celo blockchain integration ---
# Disabled by default: transactions get a simulated SHA-256 hash until a
# NjangiLedger contract has been deployed and funded (see
# blockchain_contracts/README.md). Set BLOCKCHAIN_ENABLED=True and the
# variables below once that's done.
BLOCKCHAIN_ENABLED = config('BLOCKCHAIN_ENABLED', default=False, cast=bool)
CELO_NETWORK = config('CELO_NETWORK', default='alfajores')
CELO_RPC_URL = config('CELO_RPC_URL', default='https://alfajores-forno.celo-testnet.org')
CELO_PRIVATE_KEY = config('CELO_PRIVATE_KEY', default='')
CELO_LEDGER_CONTRACT_ADDRESS = config('CELO_LEDGER_CONTRACT_ADDRESS', default='')
CELO_EXPLORER_BASE_URL = config(
    'CELO_EXPLORER_BASE_URL',
    default='https://alfajores.celoscan.io/tx/',
)

# --- MTN MoMo webhook ---
# Shared secret the payment provider must send back in the
# `X-Momo-Signature` header. Used while the real MTN MoMo Collections API
# integration is stubbed out.
MOMO_WEBHOOK_SECRET = config('MOMO_WEBHOOK_SECRET', default='dev-momo-secret')

# --- Push notifications (Firebase Cloud Messaging) ---
# Optional: when unset, push sending is a no-op and only in-app notifications
# are created. Set FCM_SERVER_KEY to your Firebase project's Cloud Messaging
# server key to enable real device pushes.
FCM_SERVER_KEY = config('FCM_SERVER_KEY', default='')
