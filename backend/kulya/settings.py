"""Kulya settings. Everything comes from environment variables (see /.env.example)."""

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load the repo-root .env (never committed) without overriding real environment variables.
_ENV_FILE = BASE_DIR.parent / ".env"
if _ENV_FILE.is_file():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _key, _sep, _value = _line.partition("=")
        if _sep and not _key.lstrip().startswith("#"):
            os.environ.setdefault(_key.strip(), _value.strip())


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG")
DEMO_MODE = env_bool("DEMO_MODE", True)

_DEV_KEY = "dev-only-not-a-secret-change-me-in-the-environment"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or _DEV_KEY
if SECRET_KEY == _DEV_KEY and not (DEBUG or DEMO_MODE):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set outside DEBUG/DEMO_MODE.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "core",
    "clinical",
    "ai",
    "workflow",
    "nutrition",
    "assistant",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "kulya.urls"
WSGI_APPLICATION = "kulya.wsgi.application"
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


def database_from_url(url: str) -> dict:
    u = urlparse(url)
    if u.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL URL (pgvector is required).")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": unquote(u.username or ""),
        "PASSWORD": unquote(u.password or ""),
        "HOST": u.hostname or "",
        "PORT": str(u.port or ""),
        "CONN_MAX_AGE": 60,
    }


# Default matches `docker compose up -d db` (loopback port 5433).
DATABASES = {
    "default": database_from_url(
        os.environ.get("DATABASE_URL") or "postgres://kulya:kulya-dev-only@127.0.0.1:5433/kulya"
    )
}

AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = os.environ.get("TIME_ZONE", "Asia/Baghdad")
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    # Default deny: every view must also declare which roles may use it (core.permissions.RolePolicy).
    "DEFAULT_PERMISSION_CLASSES": ["core.permissions.RolePolicy"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": ["rest_framework.filters.OrderingFilter"],
    "EXCEPTION_HANDLER": "core.errors.exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("THROTTLE_ANON", "60/min"),
        "user": os.environ.get("THROTTLE_USER", "600/min"),
        "login": os.environ.get("THROTTLE_LOGIN", "10/min"),
        "ai": os.environ.get("THROTTLE_AI", "30/min"),
    },
}
# Rate limits are counted in the cache. One Redis cache makes them hold across server processes.
if os.environ.get("CACHE_URL"):
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.environ["CACHE_URL"]}
    }
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("ACCESS_TOKEN_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=int(os.environ.get("REFRESH_TOKEN_HOURS", "12"))),
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Kulya API",
    "DESCRIPTION": "Dialysis documentation review and session summaries. Synthetic data only. Not a medical device.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Background jobs -------------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6380/0")
CELERY_RESULT_BACKEND = None
# Eager by default so a bare `runserver` works without a worker; docker compose sets this to false.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 120
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {"socket_connect_timeout": 2, "socket_timeout": 2}

# --- AI --------------------------------------------------------------------------------------------
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock")  # mock | anthropic
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-opus-5-5")
LLM_EFFORT = os.environ.get("LLM_EFFORT", "low")
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "45"))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# USDA FoodData Central. Empty = lookups are off and only the local catalogue is used.
USDA_API_KEY = os.environ.get("USDA_API_KEY", "")
EMBEDDING_DIMENSIONS = 256
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "4"))
RAG_MIN_SIMILARITY = float(os.environ.get("RAG_MIN_SIMILARITY", "0.12"))
# Documentation-check tolerance (minutes) between prescribed and documented duration. A workflow
# setting for the demo, not a clinical threshold.
DURATION_TOLERANCE_MINUTES = int(os.environ.get("DURATION_TOLERANCE_MINUTES", "15"))

# --- Production hardening (active whenever DEBUG is off) -------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)  # true behind an HTTPS proxy
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
    SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Only ids and event names are logged, never clinical content."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name}
        payload["msg"] = record.getMessage()
        payload.update(getattr(record, "ctx", {}))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": JsonFormatter}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
