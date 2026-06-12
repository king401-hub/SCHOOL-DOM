# backend/config/settings/base.py
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE lines into os.environ if they are not already set."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


# Allow a local .env at repo root or backend/.env for developer convenience.
for candidate in (BASE_DIR / ".env", BASE_DIR / "backend" / ".env"):
    load_env_file(candidate)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

DEBUG = env_bool('DEBUG', True)
# Keep local setup zero-config unless PostgreSQL is explicitly requested.
USE_SQLITE_FOR_DEV = env_bool('USE_SQLITE_FOR_DEV', True)

# Hosts / CSRF / CORS
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', '*')
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['*']:
    # Accept all hosts during development so phones on the LAN can reach :8000
    ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = env_list(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173,https://schooldom.academy'
)
USE_X_FORWARDED_HOST = env_bool('USE_X_FORWARDED_HOST', True)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Optional IP allowlist. Keep disabled until IP_WHITELIST contains your current public IP.
IP_WHITELIST_ENABLED = env_bool('IP_WHITELIST_ENABLED', False)
IP_WHITELIST_RANGES = env_list('IP_WHITELIST', '')
IP_WHITELIST_USE_X_FORWARDED_FOR = env_bool('IP_WHITELIST_USE_X_FORWARDED_FOR', True)

# apps that exist in every tenant (shared across all schools)
SHARED_APPS = [
    'django_tenants', 
    'core',  # must be here because it contains the tenant model
    'settings_app',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

TENANT_APPS = [
    'users',
    'schools',
    'exams',
    'academic',
    'notifications',
    'finance',
    'fee_collections',
    'hr',
    'quizzes',
    'analytics',
    'attendance',
    'django_otp',
    'django_otp.plugins.otp_email',
    'rest_framework',
    'corsheaders',
    'django_filters',
]

if USE_SQLITE_FOR_DEV:
    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django_otp',
        'django_otp.plugins.otp_email',
        'django_htmx',
        'rest_framework',
        'corsheaders',
        'core',
        'settings_app',
        'tenants',
        'users',
        'academic',
        'exams',
        'notifications',
        'finance',
        'fee_collections',
        'hr',
        'quizzes',
        'attendance',
        'superadmin_dashboard',
    ]
else:
    INSTALLED_APPS = SHARED_APPS + [
        app for app in TENANT_APPS if app not in SHARED_APPS
    ] + [
        'django_htmx',
        'tenants',
    ]

# middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'middleware.ip_whitelist.IPWhitelistMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # 'django.middleware.csrf.CsrfViewMiddleware',  # Temporarily disabled for testing
    'middleware.invalid_uuid_session.InvalidUUIDSessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

if not USE_SQLITE_FOR_DEV:
    MIDDLEWARE.insert(0, 'django_tenants.middleware.main.TenantMainMiddleware')  # must be first

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'backend' / 'config' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database Configuration
if USE_SQLITE_FOR_DEV:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    DATABASE_ROUTERS = []
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django_tenants.postgresql_backend',
            'NAME': os.getenv('DB_NAME', 'virtual_school'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'ATOMIC_REQUESTS': True,
        }
    }
    DATABASE_ROUTERS = ('django_tenants.routers.TenantSyncRouter',)

# Tenant Configuration
TENANT_MODEL = "core.SchoolTenant"
TENANT_DOMAIN_MODEL = "core.Domain"
TENANT_SUBFOLDER_PREFIX = "schools"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'users.User'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,  # Allow old tokens briefly to prevent race conditions
    'USERNAME_FIELD': 'email',
}

# Email
# OTP codes are sent only to the recipient email. Configure these env vars with
# your school's SMTP provider before using admin OTP verification.
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend',
)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'SchoolDom <noreply@schooldom.local>')
INAPPROPRIATE_QUESTION_REPORT_EMAIL = os.environ.get('INAPPROPRIATE_QUESTION_REPORT_EMAIL', '')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', False)
EMAIL_TIMEOUT = env_int('EMAIL_TIMEOUT', 10)
OTP_EMAIL_TOKEN_VALIDITY = int(os.environ.get('OTP_EMAIL_TOKEN_VALIDITY', '600'))
OTP_EMAIL_THROTTLE_FACTOR = int(os.environ.get('OTP_EMAIL_THROTTLE_FACTOR', '1'))
ADMIN_OTP_ENABLED = env_bool('ADMIN_OTP_ENABLED', False)
ADMIN_OTP_EMAIL_FAILURE_CONSOLE_FALLBACK = env_bool(
    'ADMIN_OTP_EMAIL_FAILURE_CONSOLE_FALLBACK',
    DEBUG,
)
ADMIN_OTP_DEBUG_CODE_ENABLED = env_bool('ADMIN_OTP_DEBUG_CODE_ENABLED', False)

# Payments
PAYMENT_PROVIDER = os.getenv('PAYMENT_PROVIDER', 'flutterwave').strip().lower()

# Flutterwave
FLUTTERWAVE_TEST_MODE = env_bool('FLUTTERWAVE_TEST_MODE', False)

if FLUTTERWAVE_TEST_MODE:
    FLUTTERWAVE_SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY_TEST') or os.getenv('FLUTTERWAVE_SECRET_KEY')
    FLUTTERWAVE_PUBLIC_KEY = os.getenv('FLUTTERWAVE_PUBLIC_KEY_TEST') or os.getenv('FLUTTERWAVE_PUBLIC_KEY')
else:
    FLUTTERWAVE_SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY_LIVE') or os.getenv('FLUTTERWAVE_SECRET_KEY')
    FLUTTERWAVE_PUBLIC_KEY = os.getenv('FLUTTERWAVE_PUBLIC_KEY_LIVE') or os.getenv('FLUTTERWAVE_PUBLIC_KEY')

FLUTTERWAVE_BASE_URL = os.getenv('FLUTTERWAVE_BASE_URL', 'https://developersandbox-api.flutterwave.com')
FLUTTERWAVE_CALLBACK_URL = os.getenv('FLUTTERWAVE_CALLBACK_URL', '')
FLUTTERWAVE_WEBHOOK_SECRET_HASH = os.getenv('FLUTTERWAVE_WEBHOOK_SECRET_HASH', '')
FLUTTERWAVE_AUTO_SETTLE_SCHOOL_FEES = env_bool('FLUTTERWAVE_AUTO_SETTLE_SCHOOL_FEES', True)
FLUTTERWAVE_CUSTOMER_ENDPOINT = os.getenv('FLUTTERWAVE_CUSTOMER_ENDPOINT', '/customers')
FLUTTERWAVE_VIRTUAL_ACCOUNT_ENDPOINT = os.getenv('FLUTTERWAVE_VIRTUAL_ACCOUNT_ENDPOINT', '/virtual-accounts')
FLUTTERWAVE_REQUEST_TIMEOUT = env_int('FLUTTERWAVE_REQUEST_TIMEOUT', 25)
FLUTTERWAVE_SCENARIO_KEY = os.getenv('FLUTTERWAVE_SCENARIO_KEY', '')

# Kuda
KUDA_BASE_URL = os.getenv('KUDA_BASE_URL', '').rstrip('/')
KUDA_API_KEY = os.getenv('KUDA_API_KEY', '')
KUDA_CLIENT_ID = os.getenv('KUDA_CLIENT_ID', '')
KUDA_CLIENT_SECRET = os.getenv('KUDA_CLIENT_SECRET', '')
KUDA_WEBHOOK_SECRET = os.getenv('KUDA_WEBHOOK_SECRET', '')
KUDA_TRANSFER_ENDPOINT = os.getenv('KUDA_TRANSFER_ENDPOINT', '/transfers')
KUDA_TRANSACTION_VERIFY_ENDPOINT = os.getenv('KUDA_TRANSACTION_VERIFY_ENDPOINT', '/transactions/{reference}')
KUDA_VIRTUAL_ACCOUNT_ENDPOINT = os.getenv('KUDA_VIRTUAL_ACCOUNT_ENDPOINT', '/virtual-accounts')
KUDA_COLLECTION_ACCOUNT_NUMBER = os.getenv('KUDA_COLLECTION_ACCOUNT_NUMBER', '')
KUDA_COLLECTION_ACCOUNT_NAME = os.getenv('KUDA_COLLECTION_ACCOUNT_NAME', 'SchoolDom')
KUDA_COLLECTION_BANK_NAME = os.getenv('KUDA_COLLECTION_BANK_NAME', 'Kuda Microfinance Bank')
KUDA_REQUEST_TIMEOUT = env_int('KUDA_REQUEST_TIMEOUT', 25)
WHATSAPP_BUSINESS_PHONE_NUMBER_ID = os.getenv('WHATSAPP_BUSINESS_PHONE_NUMBER_ID', '1765487408026869')
WHATSAPP_BUSINESS_ACCESS_TOKEN = os.getenv('WHATSAPP_BUSINESS_ACCESS_TOKEN', '')
WHATSAPP_BUSINESS_VERIFY_TOKEN = os.getenv('WHATSAPP_BUSINESS_VERIFY_TOKEN', '')
SCHOOLDOM_BANK_WEBHOOK_SECRET = os.getenv('SCHOOLDOM_BANK_WEBHOOK_SECRET', '')
SCHOOLDOM_PAY_BASE_URL = os.getenv('SCHOOLDOM_PAY_BASE_URL', 'https://pay.schoolom.ng')

# KudiSMS bulk SMS configuration. Schools may also set a Custom SMSConfiguration
# in admin; that tenant-level configuration takes priority over these defaults.
KUDISMS_TOKEN = os.getenv('KUDISMS_TOKEN', '')
KUDISMS_SENDER_ID = os.getenv('KUDISMS_SENDER_ID', 'neo')
KUDISMS_GATEWAY = os.getenv('KUDISMS_GATEWAY', '2')

if PAYMENT_PROVIDER == 'flutterwave' and not FLUTTERWAVE_SECRET_KEY:
    missing = [
        name for name, value in (
            ('FLUTTERWAVE_SECRET_KEY', FLUTTERWAVE_SECRET_KEY),
        )
        if not value
    ]
    raise ValueError(f"Missing required Flutterwave env vars: {', '.join(missing)}")
FLUTTERWAVE_PUBLIC_KEY = FLUTTERWAVE_PUBLIC_KEY or ''

# CORS Settings
# Allow all during dev; override via env for stricter setups
CORS_ALLOW_ALL_ORIGINS = True  # For development
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS',
    "http://localhost:5173,http://127.0.0.1:5173,https://schooldom.academy"
)

# File Uploads
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Custom settings
MAX_UPLOAD_SIZE = env_int('MAX_UPLOAD_SIZE', 52428800)  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int('FILE_UPLOAD_MAX_MEMORY_SIZE', 2621440)
OFFLINE_EXAM_EXPIRY_DAYS = 30
FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', 'https://schooldom.academy')
FRONTEND_DEV_PORT = os.getenv('FRONTEND_DEV_PORT', '5173')
NGROK_PUBLIC_URL = os.getenv('NGROK_PUBLIC_URL', '')

# Celery / Redis
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = env_int('CELERY_TASK_TIME_LIMIT', 30 * 60)
CELERY_BEAT_SCHEDULE = {
    'schooldom-daily-fee-settlement': {
        'task': 'fee_collections.tasks.run_collection_settlement_cycle',
        'schedule': 60 * 60 * 24,
    },
}
