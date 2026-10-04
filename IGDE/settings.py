"""
Django settings for IGDE.

IGDE is a *local* tool: it browses the user's filesystem and launches ACE
processes, so by default it only answers on loopback addresses and keeps
its state (database, secret key, compiled grammars) in a per-user data
directory, ``$IGDE_HOME`` (default ``~/.igde``).
"""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

IGDE_HOME = Path(os.environ.get("IGDE_HOME", Path.home() / ".igde")).expanduser()
IGDE_HOME.mkdir(parents=True, exist_ok=True)

# Built React app (``npm run build`` in frontend/)
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"


def _secret_key():
    if os.environ.get("IGDE_SECRET_KEY"):
        return os.environ["IGDE_SECRET_KEY"]
    path = IGDE_HOME / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(50))
        path.chmod(0o600)
    return path.read_text().strip()


SECRET_KEY = _secret_key()

DEBUG = os.environ.get("IGDE_DEBUG", "1") not in ("0", "false", "False")

# Only loopback hosts by default; this also defeats DNS-rebinding attacks
# against the local server.
ALLOWED_HOSTS = os.environ.get(
    "IGDE_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
).split(",")

# The Vite dev server proxies /api to Django; let its origin pass CSRF.
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "IGDE_CSRF_TRUSTED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

INSTALLED_APPS = [
    # auth is only needed by the v0.1 migrations of ``core``.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "IGDE.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    },
]

WSGI_APPLICATION = "IGDE.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("IGDE_DATABASE", str(IGDE_HOME / "igde.sqlite3")),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [FRONTEND_DIST] if FRONTEND_DIST.exists() else []

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"core": {"handlers": ["console"], "level": "INFO"}},
}

CSRF_FAILURE_VIEW = "core.views.csrf_failure"
