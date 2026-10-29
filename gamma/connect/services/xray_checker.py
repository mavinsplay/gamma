"""Клиент Xray Checker API: статусы конфигов в подписке.

Эндпоинты (см. /api/v1/docs чекера): public/proxies без авторизации,
полный /proxies — по HTTP Basic. Бэкенд ходит авторизованным запросом
и отдаёт чувствительные поля (server/port) только админу.

Ответы кэшируются на 60 секунд — фронт опрашивает sync-data-api чаще.
"""

import logging
import re

from django.conf import settings
from django.core.cache import cache
import requests

logger = logging.getLogger(__name__)

__all__ = ["get_checker_proxies", "is_checker_configured"]

CACHE_KEY = "xray_checker:proxies"
CACHE_TTL = 60

# Хвост имени конфига -> ISO-код страны (для флага в админке).
# Совпадение только по целому токену, поэтому мусор не матчится.
_COUNTRY_BY_TOKEN = {
    "usa": "us",
    "us": "us",
    "america": "us",
    "germany": "de",
    "deutschland": "de",
    "de": "de",
    "netherlands": "nl",
    "holland": "nl",
    "nl": "nl",
    "france": "fr",
    "fr": "fr",
    "finland": "fi",
    "fi": "fi",
    "sweden": "se",
    "se": "se",
    "norway": "no",
    "no": "no",
    "poland": "pl",
    "pl": "pl",
    "uk": "gb",
    "britain": "gb",
    "gb": "gb",
    "england": "gb",
    "ireland": "ie",
    "ie": "ie",
    "spain": "es",
    "es": "es",
    "italy": "it",
    "it": "it",
    "portugal": "pt",
    "pt": "pt",
    "switzerland": "ch",
    "ch": "ch",
    "austria": "at",
    "at": "at",
    "czechia": "cz",
    "czech": "cz",
    "cz": "cz",
    "romania": "ro",
    "ro": "ro",
    "bulgaria": "bg",
    "bg": "bg",
    "hungary": "hu",
    "hu": "hu",
    "greece": "gr",
    "gr": "gr",
    "turkey": "tr",
    "tr": "tr",
    "russia": "ru",
    "ru": "ru",
    "ukraine": "ua",
    "ua": "ua",
    "kazakhstan": "kz",
    "kz": "kz",
    "moldova": "md",
    "md": "md",
    "latvia": "lv",
    "lv": "lv",
    "lithuania": "lt",
    "lt": "lt",
    "estonia": "ee",
    "ee": "ee",
    "georgia": "ge",
    "ge": "ge",
    "armenia": "am",
    "am": "am",
    "azerbaijan": "az",
    "az": "az",
    "israel": "il",
    "il": "il",
    "uae": "ae",
    "ae": "ae",
    "dubai": "ae",
    "india": "in",
    "in": "in",
    "singapore": "sg",
    "sg": "sg",
    "japan": "jp",
    "jp": "jp",
    "korea": "kr",
    "kr": "kr",
    "hongkong": "hk",
    "hk": "hk",
    "canada": "ca",
    "ca": "ca",
    "mexico": "mx",
    "mx": "mx",
    "brazil": "br",
    "br": "br",
    "argentina": "ar",
    "ar": "ar",
    "chile": "cl",
    "cl": "cl",
    "australia": "au",
    "au": "au",
    "zealand": "nz",
    "nz": "nz",
    "serbia": "rs",
    "rs": "rs",
    "croatia": "hr",
    "hr": "hr",
    "slovakia": "sk",
    "sk": "sk",
    "slovenia": "si",
    "si": "si",
    "belgium": "be",
    "be": "be",
    "denmark": "dk",
    "dk": "dk",
    "iceland": "is",
    "is": "is",
}


def _country_from_name(name):
    """(iso_code, display_name): страна по эмодзи-флагу или токену имени.

    "xray-USA 🇺🇸" -> ("us", "xray-USA"),
    "whitelist-xhttp-USA us" -> ("us", "whitelist-xhttp-USA"),
    "DE-1" -> ("de", "1").
    """
    text = str(name or "").strip()
    if not text:
        return None, text

    # Эмодзи-флаг (два regional indicator) — браузеры без эмодзи-шрифта
    # рисуют его парой букв, поэтому ищем по коду, а не по виду.
    match = re.search(r"([\U0001F1E6-\U0001F1FF]{2})", text)
    if match:
        try:
            code = "".join(
                chr(ord(char) - 127397) for char in match.group(1)
            ).lower()
        except (TypeError, ValueError):
            code = ""

        if len(code) == 2 and code.isalpha():
            display = (text[: match.start()] + text[match.end() :]).strip(
                " -_|",
            )
            return code, display or text

    tokens = [t for t in re.split(r"[\s\-_]+", text) if t]
    if not tokens:
        return None, text

    if len(tokens) == 1:
        code = _COUNTRY_BY_TOKEN.get(tokens[0].lower())
        return (code, text) if code else (None, text)

    for idx in (len(tokens) - 1, 0):
        code = _COUNTRY_BY_TOKEN.get(tokens[idx].lower())
        if not code:
            continue

        if idx == len(tokens) - 1:
            display = re.sub(r"[\s\-_]+[^\s\-_]+[\s\-_]*$", "", text)
        else:
            display = re.sub(r"^[^\s\-_]+[\s\-_]+", "", text)

        return code, display.strip() or text

    return None, text


def is_checker_configured():
    """True, если задан URL чекера (логин/пароль опциональны)."""
    return bool(getattr(settings, "XRAY_CHECKER_URL", ""))


def _request(path, timeout):
    base = getattr(settings, "XRAY_CHECKER_URL", "").rstrip("/")
    if not base:
        return None, "disabled"

    user = getattr(settings, "XRAY_CHECKER_USER", "")
    password = getattr(settings, "XRAY_CHECKER_PASSWORD", "")
    try:
        resp = requests.get(
            f"{base}{path}",
            auth=(user, password) if (user or password) else None,
            timeout=timeout,
        )
    except requests.RequestException as e:
        logger.warning("[xray-checker] connection error %s: %s", path, e)
        return None, "connection_error"

    if resp.status_code == 401:
        logger.warning("[xray-checker] auth failed for %s", path)
        return None, "auth_error"

    try:
        payload = resp.json()
    except ValueError:
        logger.warning("[xray-checker] bad json for %s", path)
        return None, "bad_response"

    if not isinstance(payload, dict):
        return None, "bad_response"

    if not resp.ok or not payload.get("success", False):
        error = payload.get("error") or "api_error"
        logger.warning("[xray-checker] api error %s: %s", path, error)
        return None, "api_error"

    return payload.get("data"), None


def _normalize(proxy):
    labels = proxy.get("metricsLabels") or {}
    if not isinstance(labels, dict):
        labels = {}

    server = proxy.get("server") or ""
    port = proxy.get("port") or 0
    country_code, display_name = _country_from_name(proxy.get("name"))
    try:
        latency = (
            int(proxy["latencyMs"])
            if proxy.get("latencyMs") is not None
            else None
        )
    except (TypeError, ValueError):
        latency = None

    try:
        last_check = int(proxy.get("lastCheck") or 0)
    except (TypeError, ValueError):
        last_check = 0

    return {
        "stableId": str(proxy.get("stableId") or ""),
        "name": str(proxy.get("name") or ""),
        "displayName": display_name,
        "countryCode": country_code,
        "subName": str(proxy.get("subName") or ""),
        "groupName": str(proxy.get("groupName") or ""),
        "protocol": str(proxy.get("protocol") or "").lower(),
        "address": (f"{server}:{port}" if server and port else str(server)),
        "online": bool(proxy.get("online")),
        "latencyMs": latency,
        "lastCheck": last_check,
        "location": str(labels.get("location") or ""),
    }


def get_checker_proxies(timeout=8):
    """Список конфигов чекера. Возвращает (proxies, error), не бросает."""
    if not is_checker_configured():
        return [], "disabled"

    try:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached
    except Exception:
        pass

    data, error = _request("/api/v1/proxies", timeout)
    if error or not isinstance(data, list):
        return [], error or "bad_response"

    proxies = []
    for raw in data:
        if not isinstance(raw, dict):
            continue

        proxy = _normalize(raw)
        if proxy["stableId"]:
            proxies.append(proxy)

    try:
        cache.set(CACHE_KEY, (proxies, None), CACHE_TTL)
    except Exception:
        pass

    return proxies, None
