"""
Django settings for sapl project.

Generated by 'django-admin startproject' using Django 1.8.2.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/

Quick-start development settings - unsuitable for production
See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

"""
import logging
import socket
import sys

from decouple import config
from dj_database_url import parse as db_url
from easy_thumbnails.conf import Settings as thumbnail_settings
from unipath import Path

logging.captureWarnings(True)

host = socket.gethostbyname_ex(socket.gethostname())[0]

BASE_DIR = Path(__file__).ancestor(1)
PROJECT_DIR = Path(__file__).ancestor(2)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='')
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

ALLOWED_HOSTS = ['*']

LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/login/?next='

SAPL_VERSION = '3.1.163-RC15'

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# SAPL business apps in dependency order
SAPL_APPS = (
    'sapl.audiencia',
    'sapl.base',
    'sapl.crud',
    'sapl.parlamentares',
    'sapl.comissoes',
    'sapl.materia',
    'sapl.norma',
    'sapl.sessao',
    'sapl.lexml',
    'sapl.painel',
    'sapl.protocoloadm',
    'sapl.compilacao',
    'sapl.api',
    'sapl.rules'
)

INSTALLED_APPS = (
    'django_admin_bootstrapped',  # must come before django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',

    'crispy_forms',
    'floppyforms',

    'drf_spectacular',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',

    'easy_thumbnails',
    'image_cropping',

    'haystack',
    'django.contrib.postgres',

    'webpack_loader',

    'django_prometheus',

) + SAPL_APPS

# FTS = Full Text Search
# Desabilita a indexação textual até encontramos uma solução para a issue
# https://github.com/interlegis/sapl/issues/2055
HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.BaseSignalProcessor'  # Disable auto index
SEARCH_BACKEND = ''
SEARCH_URL = ['', '']

# SOLR
USE_SOLR = config('USE_SOLR', cast=bool, default=False)
SOLR_URL = config('SOLR_URL', cast=str, default='http://localhost:8983')
SOLR_COLLECTION = config('SOLR_COLLECTION', cast=str, default='sapl')

if USE_SOLR:
    HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'  # enable auto-index
    SEARCH_BACKEND = 'haystack.backends.solr_backend.SolrEngine'
    SEARCH_URL = ('URL', '{}/solr/{}'.format(SOLR_URL, SOLR_COLLECTION))

#  BATCH_SIZE: default is 1000 if omitted, avoid Too Large Entity Body errors
HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': SEARCH_BACKEND,
        SEARCH_URL[0]: SEARCH_URL[1],
        'BATCH_SIZE': 1000,
        'TIMEOUT': 20,
    },
}

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]
if DEBUG:
    INSTALLED_APPS += ('debug_toolbar',)
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware', ]
    INTERNAL_IPS = ('127.0.0.1')

SITE_URL = config('SITE_URL', cast=str, default='')

REST_FRAMEWORK = {
    "UNICODE_JSON": False,
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser"
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "sapl.api.permissions.SaplModelPermissions",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        'rest_framework.authentication.TokenAuthentication',
        "rest_framework.authentication.SessionAuthentication",
    ),

    'DEFAULT_SCHEMA_CLASS': 'sapl.api.schema.Schema',

    "DEFAULT_PAGINATION_CLASS": "sapl.api.pagination.StandardPagination",

    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
}

DRFAUTOAPI = {
    'DEFAULT_SERIALIZER_MODULE': 'sapl.api.serializers',
    'DEFAULT_FILTER_MODULE': 'sapl.api.forms',
    'GLOBAL_SERIALIZER_MIXIN': 'sapl.api.serializers.SaplSerializerMixin',
    'GLOBAL_FILTERSET_MIXIN': 'sapl.api.forms.SaplFilterSetMixin'
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Sapl API - docs',
    'DESCRIPTION': 'Sapl API  - Docs',
    'VERSION': '1.0.0',
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/tmp/django_cache',
    }
}

ROOT_URLCONF = 'sapl.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['sapl/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                'django.contrib.messages.context_processors.messages',
                'sapl.context_processors.parliament_info',
                'sapl.context_processors.mail_service_configured',
                'sapl.context_processors.google_recaptcha_configured',
                'sapl.context_processors.sapl_as_sapn',

            ],
            'debug': DEBUG
        },
    },
]

WSGI_APPLICATION = 'sapl.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

DATABASES = {
    'default': config(
        'DATABASE_URL', default='sqlite://:memory:',
        cast=db_url,
    )
}

IMAGE_CROPPING_JQUERY_URL = None
THUMBNAIL_PROCESSORS = (
    'image_cropping.thumbnail_processors.crop_corners',
) + thumbnail_settings.THUMBNAIL_PROCESSORS

THUMBNAIL_SOURCE_GENERATORS = (
    'sapl.utils.pil_image',
)

# troque no caso de reimplementação da classe User conforme
# https://docs.djangoproject.com/en/1.9/topics/auth/customizing/#substituting-a-custom-user-model
AUTH_USER_MODEL = 'auth.User'

X_FRAME_OPTIONS = 'ALLOWALL'

EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', cast=int, default=587)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool, default=True)
EMAIL_SEND_USER = config('EMAIL_SEND_USER', cast=str, default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', cast=str, default='')
SERVER_EMAIL = config('SERVER_EMAIL', cast=str, default='')
EMAIL_RUNNING = None

MAX_DOC_UPLOAD_SIZE = 150 * 1024 * 1024  # 150MB
MAX_IMAGE_UPLOAD_SIZE = 2 * 1024 * 1024  # 2MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/
LANGUAGE_CODE = 'pt-br'
LANGUAGES = (
    ('pt-br', 'Português'),
)

TIME_ZONE = config('TZ', default='America/Sao_Paulo')
if not TIME_ZONE:
    raise ValueError(
        'TIMEZONE env variable undefined in .env settings file! Leaving...')

USE_I18N = True
USE_L10N = True
USE_TZ = True
# DATE_FORMAT = 'N j, Y'
DATE_FORMAT = 'd/m/Y'
SHORT_DATE_FORMAT = 'd/m/Y'
DATETIME_FORMAT = 'd/m/Y H:i:s'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'
DATE_INPUT_FORMATS = ('%d/%m/%Y', '%m-%d-%Y', '%Y-%m-%d')

LOCALE_PATHS = (
    'locale',
)

WEBPACK_LOADER = {
    'DEFAULT': {
        'CACHE': not DEBUG,
        'BUNDLE_DIR_NAME': 'sapl/static/sapl/frontend',
        'STATS_FILE': PROJECT_DIR.child('frontend').child(f'{"dev-" if DEBUG else ""}webpack-stats.json'),
        'POLL_INTERVAL': 0.1,
        'TIMEOUT': None,
        'IGNORE': [r'.+\.hot-update.js', r'.+\.map']
    }
}
if DEBUG and not WEBPACK_LOADER['DEFAULT']['STATS_FILE'].exists():
    WEBPACK_LOADER['DEFAULT']['STATS_FILE'] = PROJECT_DIR.child(
        'frontend').child(f'webpack-stats.json')

STATIC_URL = '/static/'
STATIC_ROOT = PROJECT_DIR.child("collected_static")

STATICFILES_DIRS = (
    BASE_DIR.child('static'),
)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

MEDIA_ROOT = PROJECT_DIR.child("media")
MEDIA_URL = '/media/'

FILE_UPLOAD_PERMISSIONS = 0o644

DAB_FIELD_RENDERER = \
    'django_admin_bootstrapped.renderers.BootstrapFieldRenderer'
CRISPY_TEMPLATE_PACK = 'bootstrap4'
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap4'
CRISPY_FAIL_SILENTLY = not DEBUG
FLOPPY_FORMS_USE_GIS = False

FORM_RENDERER = 'django.forms.renderers.DjangoTemplates'

# suprime texto de ajuda default do django-filter
FILTERS_HELP_TEXT_FILTER = False

LOGGING_CONSOLE_VERBOSE = config(
    'LOGGING_CONSOLE_VERBOSE', cast=bool, default=False)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s ' + host + ' %(pathname)s %(name)s:%(funcName)s:%(lineno)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(asctime)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'filters': ['require_debug_true'],
            'formatter': 'simple',
        },
        'console_verbose': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'filters': ['require_debug_true'],
            'formatter': 'verbose',
        },
        'applogfile': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'sapl.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'sapl': {
            'handlers': ['applogfile'] + ['console_verbose'] if LOGGING_CONSOLE_VERBOSE else [],
            'level': 'DEBUG' if LOGGING_CONSOLE_VERBOSE else 'INFO',
            'propagate': True,
        },
        'django': {
            'handlers': ['applogfile'] + ['console_verbose'] if LOGGING_CONSOLE_VERBOSE else [],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',  # default
    'sapl.hashers.ZopeSHA1PasswordHasher',
]

LOGOUT_REDIRECT_URL = '/login'
