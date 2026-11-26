"""Django settings for MEBELCHI AI. All secrets come from environment variables."""
import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(env(key, str(default))).lower() in ("1", "true", "yes", "on")


def env_list(key, default=""):
    return [x.strip() for x in env(key, default).split(",") if x.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
TESTING = "test" in sys.argv

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or TESTING:
        SECRET_KEY = "insecure-dev-only-key-do-not-use-in-production-0123456789abcdef"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "apps.core",
    "apps.users",
    "apps.accounts",
    "apps.workspaces",
    "apps.projects",
    "apps.materials",
    "apps.furniture",
    "apps.calculations",
    "apps.cutting_lists",
    "apps.geometry",
    "apps.designs",
    "apps.conversations",
    "apps.galleries",
    "apps.files",
    "apps.integrations",
    "apps.audit",
    "apps.workshops",
    "apps.rooms",
    "apps.ai",
    "apps.finance",
    "apps.marketplace",
    "apps.subscriptions",
    "apps.notifications",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
    "apps.analytics.middleware.RequestLogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# Database: centralized selection in config/database.py (PostgreSQL first, optional SQLite fallback).
from config.database import log_database_status, resolve_database  # noqa: E402

_default_db, DATABASE_STATUS = resolve_database(os.environ, BASE_DIR)
DATABASES = {"default": _default_db}
# Optional read-only PostgreSQL role for audit archiving (deploy/sql/audit_roles.sql). Used only through `.using("audit_archiver")`;
# there is no database router, so nothing else ever touches it.
if env("AUDIT_ARCHIVER_USER") and _default_db["ENGINE"].endswith("postgresql"):
    DATABASES["audit_archiver"] = {**_default_db, "USER": env("AUDIT_ARCHIVER_USER"), "PASSWORD": env("AUDIT_ARCHIVER_PASSWORD", ""),
                                   "TEST": {"MIRROR": "default"}}
AUDIT_TABLE_WARN_MB = int(env("AUDIT_TABLE_WARN_MB", "2048"))
AUDIT_ARCHIVE_AFTER_DAYS = int(env("AUDIT_ARCHIVE_AFTER_DAYS", "365"))

AUTH_USER_MODEL = "users.User"
# Telegram bot integration. The bot authenticates to the API with TELEGRAM_BOT_API_SECRET (fail-closed when empty).
# TELEGRAM_BOT_TOKEN is used only by the backend to push notifications; the bot process has its own copy.
# AI provider layer: disabled until a provider is registered in AI_PROVIDERS and AI_PROVIDER + AI_API_KEY are set (see apps/ai/providers.py)
ORDER_REMINDER_HOURS = int(env("ORDER_REMINDER_HOURS", "4"))      # a workshop that has not answered a new order is reminded this often ...
ORDER_REMINDER_MAX = int(env("ORDER_REMINDER_MAX", "6"))          # ... at most this many times (4 h x 6 = 24 h), then the customer and admins are told once
AI_PROVIDER = env("AI_PROVIDER", "")
AI_API_KEY = env("AI_API_KEY", "")
AI_MODEL = env("AI_MODEL", "")
AI_PROVIDERS: dict[str, str] = {}
SMS_PROVIDER = env("SMS_PROVIDER", "")
SMS_PROVIDERS: dict[str, str] = {}
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_API_SECRET = env("TELEGRAM_BOT_API_SECRET", "")
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Uploads
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_FILE_UPLOAD_BYTES = 25 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
# User uploads are private (0640); collected static files must stay world-readable for nginx.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"file_permissions_mode": 0o640}},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Cache / Celery
if env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}
    CELERY_BROKER_URL = env("REDIS_URL")
    CELERY_TASK_ALWAYS_EAGER = False
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CELERY_BROKER_URL = "memory://"
    CELERY_TASK_ALWAYS_EAGER = True
CELERY_RESULT_BACKEND = None
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "prune-system-logs": {"task": "apps.analytics.tasks.prune_system_logs", "schedule": 60 * 60 * 24},
    "flush-expired-tokens": {"task": "apps.analytics.tasks.flush_expired_tokens", "schedule": 60 * 60 * 24},
    "remind-pending-orders": {"task": "apps.marketplace.tasks.remind_pending_orders", "schedule": 15 * 60},
    "check-audit-size": {"task": "apps.audit.tasks.check_audit_size", "schedule": 60 * 60 * 24},
}

# REST framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", "60/min"),
        "user": env("THROTTLE_USER", "600/min"),
        "auth": env("THROTTLE_AUTH", "10/min"),
        "export": env("THROTTLE_EXPORT", "30/min"),
        "telegram": env("THROTTLE_TELEGRAM", "120/min"),
    },
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append("rest_framework.renderers.BrowsableAPIRenderer")
if TESTING:
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {k: "10000/min" for k in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "14"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MEBELCHI AI API",
    "DESCRIPTION": "Furniture design, calculation and production automation. No external AI services.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# CORS / CSRF
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_CREDENTIALS = False  # JWT in Authorization header, no cookies

# Audit log: request header that carries the real client IP. Set to HTTP_X_REAL_IP only when every request passes through the
# nginx proxy (docker-compose does this); otherwise keep REMOTE_ADDR so clients cannot forge it.
AUDIT_IP_HEADER = env("AUDIT_IP_HEADER", "REMOTE_ADDR")

# Email (console in dev)
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "25"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "MEBELCHI AI <no-reply@mebelchi.local>")
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173")
# Google sign-in (optional). Create an OAuth "Web" client at console.cloud.google.com and put its client ID here.
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", "")

# Production hardening
if not DEBUG and not TESTING:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
log_database_status(DATABASE_STATUS)
