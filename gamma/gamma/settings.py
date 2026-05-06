import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv()

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "4f7Z7JU2q8dXOiAgR2fW1niOZTLGUexLGo3E4LL0oSi8mg1p",
)

REMNAWAVE_URL = os.getenv("REMNAWAVE_URL", "https://my-test-vpn.panel.ru")
REMNAWAVE_TOKEN = os.getenv("REMNAWAVE_TOKEN", "YOUR_BEARER_TOKEN")
REMNAWAVE_SECRET_NAME = os.getenv("REMNAWAVE_SECRET_NAME", "wBYQJWtq")
REMNAWAVE_SECRET_VALUE = os.getenv("REMNAWAVE_SECRET_VALUE", "KuOsIrYu")

DEBUG = True

MOCK_TELEGRAM_USER_DATA = json.loads(
    os.getenv(
        "MOCK_TELEGRAM_USER_DATA",
        '{"id": 123456789, "first_name": \
            "Mock", "last_name": "User", "username": "mock_user"}',
    ),
)

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(
    ",",
)

CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app",
    "https://*.loca.lt",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

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
        "NAME": "django.contrib.auth.password_validati\
            on.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_valida\
            tion.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validat\
            ion.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validat\
            ion.NumericPasswordValidator",
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
