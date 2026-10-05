"""Django settings for Kulya. All configuration comes from environment variables."""

import os
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


def database_from_url(url: str) -> dict:
    """Parse DATABASE_URL (postgres://... or sqlite:///path)."""
    u = urlparse(url)
    if u.scheme == "sqlite":
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": u.path.lstrip("/") or ":memory:"}
    if u.scheme in {"postgres", "postgresql"}:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": u.path.lstrip("/"),
            "USER": unquote(u.username or ""),
            "PASSWORD": unquote(u.password or ""),
            "HOST": u.hostname or "",
            "PORT": str(u.port or ""),
        }
    raise ImproperlyConfigured(f"Unsupported DATABASE_URL scheme: {u.scheme!r}")


DEBUG = env_bool("DJANGO_DEBUG")
DEMO_MODE = env_bool("DEMO_MODE", True)

_DEV_KEY = "dev-only-not-a-secret-change-me-in-env"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or _DEV_KEY
if SECRET_KEY == _DEV_KEY and not (DEBUG or DEMO_MODE):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set outside DEBUG/DEMO_MODE.")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",")

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))
LLM_EFFORT = os.environ.get("LLM_EFFORT", "low")  # low | medium | high | xhigh | max

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "accounts",
    "clinical",
    "ai_engine",
    "rules",
    "summaries",
    "audit",
    "seed",
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
            ],
        },
    },
]

WSGI_APPLICATION = "kulya.wsgi.application"

# SQLite is the fallback for local quick runs only; docker and CI use PostgreSQL 16.
DATABASES = {"default": database_from_url(os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "ar"
TIME_ZONE = "Asia/Baghdad"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "kulya.common.errors.exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Kulya API",
    "DESCRIPTION": "Dialysis session review support. Synthetic data only.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
}
