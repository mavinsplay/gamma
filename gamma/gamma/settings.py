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

if not DEBUG:
    # Hashed static filenames (app.a3f2b1c4.js) allow long-lived
    # browser caching; collectstatic regenerates the manifest.
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": (
                "django.contrib.staticfiles.storage"
                ".ManifestStaticFilesStorage"
            ),
        },
    }


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# YooMoney payment gateway
YOOMONEY_RECEIVER = os.getenv("YOOMONEY_RECEIVER", "")
YOOMONEY_TOKEN = os.getenv("YOOMONEY_TOKEN", "")

# Platega payment gateway (SBP / Crypto)
PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET = os.getenv("PLATEGA_SECRET", "")
# Platega Payout API: отдельный секрет из ЛК (раздел Payout API).
# Без него доступны балансы/статистика, но не вывод и не карты.
PLATEGA_PAYOUT_SECRET = os.getenv("PLATEGA_PAYOUT_SECRET", "")
# Предустановленная карта для вывода (cardId сохранённой карты).
# Если пусто — cardId выбирается в панели из списка карт.
PLATEGA_PAYOUT_CARD_ID = os.getenv("PLATEGA_PAYOUT_CARD_ID", "")


# Лимиты ручного вывода, ₽
def _env_int(name, default):
    """Число из .env без падения всего приложения при опечатке."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


PLATEGA_PAYOUT_MIN = _env_int("PLATEGA_PAYOUT_MIN", 1000)
PLATEGA_PAYOUT_MAX = _env_int("PLATEGA_PAYOUT_MAX", 87500)
# Комиссия сайта за вывод, USD (снимается с баланса сверх суммы).
PLATEGA_PAYOUT_FEE_USD = _env_float("PLATEGA_PAYOUT_FEE_USD", 0.5)
# Курс USD->RUB для оценки «вывести всё» (комиссия в рублях).
PLATEGA_USD_RUB_RATE = _env_float("PLATEGA_USD_RUB_RATE", 80.0)

# Автовывод через браузер (когда Payout API не одобрен):
# логин/пароль от личного кабинета Platega. Хранить только в .env!
PLATEGA_UI_LOGIN = os.getenv("PLATEGA_UI_LOGIN", "")
PLATEGA_UI_PASSWORD = os.getenv("PLATEGA_UI_PASSWORD", "")
# Кабинет my.platega.io. PAYOUT_URL — полный адрес раздела выводов
# (содержит ID мерчанта). Пусто — UI-вывод отключён.
PLATEGA_UI_LOGIN_URL = os.getenv(
    "PLATEGA_UI_LOGIN_URL",
    "https://my.platega.io/login",
)
PLATEGA_UI_PAYOUT_URL = os.getenv("PLATEGA_UI_PAYOUT_URL", "")
# Каталог профиля браузера (сессия, скриншоты). В compose монтируется
# volume'ом, локально — обычная папка рядом с точкой запуска.
PLATEGA_UI_PROFILE_DIR = os.getenv(
    "PLATEGA_UI_PROFILE_DIR",
    "./platega_profile",
)
# Карта-назначение для UI-вывода: последние 4 цифры сохранённой
# на сайте карты (напр. 3710). Полный PAN нигде не нужен и не хранится.
PLATEGA_PAYOUT_CARD_LAST4 = "".join(
    ch for ch in os.getenv("PLATEGA_PAYOUT_CARD_LAST4", "") if ch.isdigit()
)[-4:]
# Автовывод по порогу RUB-баланса: 1 — включён.
PLATEGA_AUTOPAYOUT_ENABLED = os.getenv("PLATEGA_AUTOPAYOUT_ENABLED", "") == "1"
PLATEGA_AUTOPAYOUT_THRESHOLD_RUB = _env_int(
    "PLATEGA_AUTOPAYOUT_THRESHOLD_RUB",
    10000,
)
# Как часто проверять порог и очередь задач, минут.
PLATEGA_AUTOPAYOUT_CHECK_MIN = _env_int("PLATEGA_AUTOPAYOUT_CHECK_MIN", 15)
# Пауза после любого вывода перед следующим авто-выводом, минут.
PLATEGA_AUTOPAYOUT_COOLDOWN_MIN = _env_int(
    "PLATEGA_AUTOPAYOUT_COOLDOWN_MIN",
    60,
)

# Комиссии провайдеров (доля от суммы, для расчёта чистого дохода)
YOOMONEY_FEE_RATE = float(os.getenv("YOOMONEY_FEE_RATE", "0.03"))
PLATEGA_FEE_RATE = float(os.getenv("PLATEGA_FEE_RATE", "0.04"))

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
