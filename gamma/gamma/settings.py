import json
import os
from pathlib import Path

from dotenv import load_dotenv

__all__ = ()

BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv()


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} must be set.")

    return value


SECRET_KEY = required_env("DJANGO_SECRET_KEY")

BOT_TOKEN = required_env("BOT_TOKEN")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "gamma_net_bot")
TELEGRAM_CLIENT_ID = os.getenv("TELEGRAM_CLIENT_ID", BOT_TOKEN.split(":")[0])
TELEGRAM_CLIENT_SECRET = os.getenv("TELEGRAM_CLIENT_SECRET", "")

REMNAWAVE_URL = os.getenv("REMNAWAVE_URL", "")
REMNAWAVE_TOKEN = os.getenv("REMNAWAVE_TOKEN", "")
REMNAWAVE_SECRET_NAME = os.getenv("REMNAWAVE_SECRET_NAME", "")
REMNAWAVE_SECRET_VALUE = os.getenv("REMNAWAVE_SECRET_VALUE", "")
WHITELIST_EXTERNAL_SQUAD_UUID = os.getenv(
    "WHITELIST_EXTERNAL_SQUAD_UUID",
    "68fce704-b469-43f4-afc9-8a38a5c8b851",
)

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"

MOCK_DATA_ENV = os.getenv("MOCK_TELEGRAM_USER_DATA")
MOCK_TELEGRAM_USER_DATA = json.loads(MOCK_DATA_ENV) if MOCK_DATA_ENV else None

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
ADMIN_URL = os.getenv("ADMIN_URL", "admin/")
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() == "true"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
if not DEBUG and "*" in ALLOWED_HOSTS:
    ALLOWED_HOSTS.remove("*")
    if not ALLOWED_HOSTS:
        raise ValueError("DJANGO_ALLOWED_HOSTS must be set in production.")

CSRF_TRUSTED_ORIGINS = os.getenv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://gamma.ru",
).split(",")

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SUPPORT_URL = "https://t.me/" + os.getenv(
    "SUPPORT_USERNAME",
    "gamma_net_bot",
).replace("@", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "shop",
    "connect",
    "user",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gamma.urls"

template_dirs = [BASE_DIR / "templates"]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": template_dirs,
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

WSGI_APPLICATION = "gamma.wsgi.application"


SELECTED_DATABASE = os.getenv(
    "DJANGO_DATABASE_SELECT",
    "postgresql" if not DEBUG else "sqlite3",
)

if SELECTED_DATABASE == "postgresql":
    DB_NAME = os.getenv("DJANGO_POSTGRESQL_NAME", "gamma")
    DB_USER = os.getenv("DJANGO_POSTGRESQL_USER", "postgres")
    DB_PASSWORD = os.getenv("DJANGO_POSTGRESQL_PASSWORD", "root")
    DB_HOST = os.getenv("DJANGO_POSTGRESQL_HOST", "localhost")
    DB_PORT = int(os.getenv("DJANGO_POSTGRESQL_PORT", "5432"))

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DB_NAME,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
        },
    }

else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        },
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation" ".MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".NumericPasswordValidator"
        ),
    },
]


LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


STATIC_ROOT = BASE_DIR / "static"

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static_dev",
]


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# YooMoney payment gateway
YOOMONEY_RECEIVER = os.getenv("YOOMONEY_RECEIVER", "")
YOOMONEY_TOKEN = os.getenv("YOOMONEY_TOKEN", "")

# Platega payment gateway (SBP / Crypto)
PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET = os.getenv("PLATEGA_SECRET", "")

ORDER_TIMEOUT_MINUTES = 10

# Redis Cache
# Priority: explicit REDIS_URL > REDIS_HOST parts > in-process LocMemCache.
REDIS_URL = os.getenv("REDIS_URL", "")

if not REDIS_URL:
    REDIS_HOST = os.getenv("REDIS_HOST", "")
    if REDIS_HOST:
        REDIS_PORT = os.getenv("REDIS_PORT", "6379")
        REDIS_DB = os.getenv("REDIS_DB", "0")
        REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
        if REDIS_PASSWORD:
            REDIS_URL = (
                f"redis://:{REDIS_PASSWORD}"
                f"@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
            )
        else:
            REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 15,
        },
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    }
