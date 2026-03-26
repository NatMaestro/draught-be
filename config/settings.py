"""
Django settings for Draught backend.
"""

import os
import sys
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, True))
environ.Env.read_env(BASE_DIR / ".env")

RUNNING_TESTS = "test" in sys.argv

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production")
DEBUG = env("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# HTTPS behind Render / other reverse proxies
if not DEBUG and not RUNNING_TESTS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "apps.users",
    "apps.authentication",
    "apps.matchmaking",
    "apps.games",
    "apps.board_engine",
    "apps.ratings",
    "apps.ai",
    "apps.social",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "config.middleware.DisableCSRFForAPIMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "users.User"

# Channel layers - Redis for production, InMemory for dev without Redis
REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
USE_REDIS_CHANNELS = env.bool("USE_REDIS_CHANNELS", default=False)
if USE_REDIS_CHANNELS:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        },
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

_db_url = env("DATABASE_URL", default="").strip()

if RUNNING_TESTS:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
elif _db_url and _db_url.startswith("postgres"):
    DATABASES = {"default": env.db("DATABASE_URL")}
    DATABASES["default"]["OPTIONS"] = {
        "connect_timeout": env.int("DATABASE_CONNECT_TIMEOUT", default=120),
    }
else:
    raise ImproperlyConfigured(
        "Set DATABASE_URL in .env to a PostgreSQL connection string (e.g. Neon postgresql://...)."
    )

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS: in production set CORS_ALLOWED_ORIGINS (comma-separated) to your frontend origin(s).
_cors_origins = env.list("CORS_ALLOWED_ORIGINS", default=[])
if _cors_origins:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = _cors_origins
else:
    CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL", default=True)

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# drf-spectacular (Swagger / OpenAPI)
SPECTACULAR_SETTINGS = {
    "TITLE": "Draught API",
    "DESCRIPTION": "API for the Draught board game: auth, matchmaking, games, moves.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

from datetime import timedelta

# JWT — access is short-lived; refresh is long-lived (client must store refresh & call /auth/token/refresh/).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_MINUTES", default=60),
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_DAYS", default=7),
    ),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
}

# ELO / Rating
ELO_K_FACTOR = env.int("ELO_K_FACTOR", default=32)
ELO_INITIAL_RATING = env.int("ELO_INITIAL_RATING", default=1000)

# Ranked matchmaking: pair within a rating gap that widens while you wait (Chess.com-style).
# See apps.matchmaking.services.ranked_effective_delta_for_elapsed
MATCHMAKING_RANKED_INITIAL_DELTA = env.int("MATCHMAKING_RANKED_INITIAL_DELTA", default=150)
MATCHMAKING_RANKED_MAX_DELTA = env.int("MATCHMAKING_RANKED_MAX_DELTA", default=500)
MATCHMAKING_RANKED_EXPAND_EVERY_SEC = env.int("MATCHMAKING_RANKED_EXPAND_EVERY_SEC", default=15)
MATCHMAKING_RANKED_EXPAND_STEP = env.int("MATCHMAKING_RANKED_EXPAND_STEP", default=25)

# Web Push (VAPID) — optional; leave empty to disable push delivery (in-app notifications still work).
# Generate keys: `pip install pywebpush` then use `pywebpush` docs or:
#   openssl ecparam -name prime256v1 -genkey -noout -out vapid_private.pem
#   and derive public key, or use an online VAPID generator for development.
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", default="")
VAPID_SUBJECT = env("VAPID_SUBJECT", default="mailto:support@example.com")

# Facebook Login — optional; used to validate tokens (debug_token) and link accounts.
FACEBOOK_APP_ID = env("FACEBOOK_APP_ID", default="")
FACEBOOK_APP_SECRET = env("FACEBOOK_APP_SECRET", default="")

# TikTok Login Kit — optional; link account via OAuth code exchange.
TIKTOK_CLIENT_KEY = env("TIKTOK_CLIENT_KEY", default="")
TIKTOK_CLIENT_SECRET = env("TIKTOK_CLIENT_SECRET", default="")
TIKTOK_REDIRECT_URI = env("TIKTOK_REDIRECT_URI", default="")
