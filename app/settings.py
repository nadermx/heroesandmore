import os
import sys
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Detect if running tests
TESTING = 'test' in sys.argv or 'pytest' in sys.modules

# Import local config
try:
    import config
except ImportError:
    raise ImportError("Missing config.py - copy from config.py.example and configure")

SECRET_KEY = config.SECRET_KEY
DEBUG = getattr(config, 'DEBUG', False)
ALLOWED_HOSTS = getattr(config, 'ALLOWED_HOSTS', [])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.postgres',
    # Third party
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'django_htmx',
    # REST API
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    # Local apps
    'api',
    'accounts',
    'user_collections',
    'items',
    'marketplace',
    'social',
    'alerts',
    'pricing',
    'scanner',
    'seller_tools',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be at top
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'app.middleware.SignupHoneypotMiddleware',
]

ROOT_URLCONF = 'app.urls'

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
                'app.context_processors.seo',
                'app.context_processors.auction_banner',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'heroesandmore',
        'USER': 'heroesandmore',
        'PASSWORD': getattr(config, 'DATABASE_PASSWORD', 'password'),
        'HOST': getattr(config, 'DATABASE_HOST', 'localhost'),
        'PORT': getattr(config, 'DATABASE_PORT', '5432'),
    }
}

# Use SQLite for development if no PostgreSQL available
if DEBUG and not os.environ.get('USE_POSTGRES'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Sites framework
SITE_ID = 1

# Authentication
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Django Allauth settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
LOGIN_URL = '/auth/signup/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Google OAuth
GOOGLE_CLIENT_ID = getattr(config, 'GOOGLE_CLIENT_ID', '')

# Apple OAuth (Sign in with Apple)
APPLE_CLIENT_ID = getattr(config, 'APPLE_CLIENT_ID', '')  # Service ID (e.g. com.heroesandmore.signin)
APPLE_TEAM_ID = getattr(config, 'APPLE_TEAM_ID', '')
APPLE_KEY_ID = getattr(config, 'APPLE_KEY_ID', '')
APPLE_CERTIFICATE = getattr(config, 'APPLE_CERTIFICATE', '')  # Private key PEM content

# Socialaccount providers
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': GOOGLE_CLIENT_ID,
            'secret': getattr(config, 'GOOGLE_CLIENT_SECRET', ''),
        },
    },
    'apple': {
        'APP': {
            'client_id': APPLE_CLIENT_ID,
            'secret': APPLE_KEY_ID,
            'settings': {
                'certificate_key': APPLE_CERTIFICATE,
            },
        },
        'SCOPE': ['name', 'email'],
    }
}
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# Redis and Celery
REDIS_URL = getattr(config, 'REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# Stripe Configuration
STRIPE_PUBLIC_KEY = getattr(config, 'STRIPE_PUBLIC_KEY', '')
STRIPE_SECRET_KEY = getattr(config, 'STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = getattr(config, 'STRIPE_WEBHOOK_SECRET', '')
STRIPE_CONNECT_WEBHOOK_SECRET = getattr(config, 'STRIPE_CONNECT_WEBHOOK_SECRET', '')

# Internal Subscription Billing Settings
# Subscription billing is handled internally via PaymentIntents (not Stripe Billing)
SUBSCRIPTION_GRACE_PERIOD_DAYS = 7  # Days before downgrading after failed payment
SUBSCRIPTION_MAX_RETRY_ATTEMPTS = 4  # Max payment retry attempts
SUBSCRIPTION_RETRY_INTERVALS = [1, 3, 5, 7]  # Days between retry attempts

# Order payment timeout (hours) before auto-canceling unpaid orders
ORDER_PAYMENT_TIMEOUT_HOURS = getattr(config, 'ORDER_PAYMENT_TIMEOUT_HOURS', 24)

# Platform fee (3% base, adjusted per seller tier)
from decimal import Decimal
PLATFORM_FEE_PERCENT = Decimal('0.03')

# Site URL for callbacks
SITE_URL = getattr(config, 'SITE_URL', 'http://localhost:8000')
if not DEBUG:
    SITE_URL = 'https://heroesandmore.com'

# DigitalOcean Spaces (for production)
USE_SPACES = getattr(config, 'USE_SPACES', False)
if USE_SPACES:
    AWS_ACCESS_KEY_ID = config.DO_SPACES_KEY
    AWS_SECRET_ACCESS_KEY = config.DO_SPACES_SECRET
    AWS_STORAGE_BUCKET_NAME = config.DO_SPACES_BUCKET
    AWS_S3_ENDPOINT_URL = config.DO_SPACES_ENDPOINT
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    AWS_DEFAULT_ACL = 'public-read'
    AWS_LOCATION = 'media'
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'{config.DO_SPACES_ENDPOINT}/{config.DO_SPACES_BUCKET}/media/'

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = getattr(config, 'EMAIL_HOST', 'localhost')
EMAIL_PORT = getattr(config, 'EMAIL_PORT', 25)
EMAIL_HOST_USER = getattr(config, 'EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = getattr(config, 'EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = getattr(config, 'EMAIL_USE_TLS', True)
DEFAULT_FROM_EMAIL = getattr(config, 'DEFAULT_FROM_EMAIL', 'noreply@heroesandmore.com')

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Security settings for production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_SSL_REDIRECT = getattr(config, 'SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = getattr(config, 'SECURE_SSL_REDIRECT', True)
    CSRF_COOKIE_SECURE = getattr(config, 'SECURE_SSL_REDIRECT', True)
    if getattr(config, 'SECURE_SSL_REDIRECT', True):
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True

# Logging - Comprehensive setup for debugging
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {module}:{lineno} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "module": "%(module)s", "line": %(lineno)d, "message": "%(message)s"}',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        # Main application log
        'app_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'app.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        # Errors only - quick access to problems
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'errors.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        # Stripe/payment logging
        'stripe_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'stripe.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        # Security events (auth, permissions)
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'security.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        # Celery tasks
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'celery_tasks.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        # Database queries (slow queries)
        'db_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'db.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
        },
        # API requests
        'api_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'api.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        # Frontend JavaScript errors
        'frontend_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'frontend.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'app_file', 'error_file'],
        'level': 'INFO',
    },
    'loggers': {
        # Django core
        'django': {
            'handlers': ['console', 'app_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Database - only log slow queries in production
        'django.db.backends': {
            'handlers': ['db_file'],
            'level': 'WARNING',  # Change to DEBUG to log all queries
            'propagate': False,
        },
        # Stripe SDK logging
        'stripe': {
            'handlers': ['console', 'stripe_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Our Stripe services
        'marketplace.services': {
            'handlers': ['console', 'stripe_file', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Seller tools (subscriptions)
        'seller_tools': {
            'handlers': ['console', 'stripe_file', 'celery_file', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Celery
        'celery': {
            'handlers': ['console', 'celery_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Our app loggers
        'accounts': {
            'handlers': ['console', 'app_file', 'security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'marketplace': {
            'handlers': ['console', 'app_file', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'pricing': {
            'handlers': ['console', 'app_file', 'celery_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'alerts': {
            'handlers': ['console', 'app_file', 'celery_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'scanner': {
            'handlers': ['console', 'app_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'api': {
            'handlers': ['console', 'api_file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Frontend JavaScript errors
        'frontend': {
            'handlers': ['console', 'frontend_file', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# Django REST Framework
from datetime import timedelta

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [] if TESTING else [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# Simple JWT settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# CORS settings
CORS_ALLOWED_ORIGINS = [
    'https://heroesandmore.com',
    'https://www.heroesandmore.com',
]

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOW_CREDENTIALS = True

# DRF Spectacular settings (API documentation)
SPECTACULAR_SETTINGS = {
    'TITLE': 'HeroesAndMore API',
    'DESCRIPTION': 'REST API for HeroesAndMore collectibles marketplace',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
