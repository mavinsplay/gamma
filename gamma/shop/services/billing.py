"""Статистика доходов и расходов для админской билинг-панели."""

import calendar
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal
import logging

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone
import requests

from shop.models import ServerExpense

logger = logging.getLogger(__name__)

__all__ = [
    "CHANNELS",
    "get_autopayout_config",
    "get_billing_stats",
    "get_blacklisted_ids",
    "get_ledger_data",
    "get_servers_data",
    "get_top_payers",
    "get_usd_rub_rate",
    "get_yoomoney_block",
    "prune_old_ledger_entries",
    "save_autopayout_config",
]


# Канал -> (подпись, провайдер, ставка комиссии берётся из настроек)
CHANNELS = (
    ("card", "Карты", "yoomoney"),
    ("sbp", "СБП", "platega"),
    ("crypto", "Крипто", "platega"),
    ("platega_other", "Platega (стар.)", "platega"),
)


YOOMONEY_CACHE_TTL = 300
USD_RUB_RATE_CACHE_KEY = "billing:usd_rub_rate"
USD_RUB_RATE_TTL = 900


def mask_account(account):
    digits = "".join(ch for ch in str(account or "") if ch.isdigit())
    if len(digits) < 8:
        return "****"

    return f"{digits[:4]} •••• {digits[-4:]}"


def get_yoomoney_block(days=30, date_from=None, date_to=None):
    """Кошелёк YooMoney: баланс + приходы по дням (для сверки).

    Кэшируется на 5 минут — история тянется несколькими запросами.
    Период — либо последние `days` дней, либо диапазон date_from..date_to.
    """
    from django.core.cache import cache

    from shop.services.yoomoney import get_account_info, get_wallet_daily

    now = timezone.now()
    tz = timezone.get_current_timezone()
    if date_from and date_to and date_from <= date_to:
        since = timezone.make_aware(
            datetime.combine(date_from, dt_time.min),
            tz,
        )
        # История будущего не существует — обрезаем по сегодня.
        end_day = min(date_to, now.date())
        end = timezone.make_aware(datetime.combine(end_day, dt_time.max), tz)
        cache_key = (
            f"billing:yoomoney:{date_from.isoformat()}:{date_to.isoformat()}"
        )
    else:
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 30

        days = max(1, min(days, 365))
        since = now - timedelta(days=days)
        end = now
        cache_key = f"billing:yoomoney:{days}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    info = get_account_info()
    if info is None:
        result = {"balance": None, "account_masked": None, "error": True}
        cache.set(cache_key, result, 60)
        return result

    daily = get_wallet_daily(since, end)
    result = {
        "balance": info["balance"],
        "account_masked": mask_account(info["account"]),
        "error": False,
        "daily": daily,
        "total": round(sum(daily.values()), 2),
    }
    cache.set(cache_key, result, YOOMONEY_CACHE_TTL)
    return result


def get_blacklisted_ids():
    """Telegram ID, скрытые из билинг-статистики."""
    from shop.models import ExcludedPayer

    return set(
        ExcludedPayer.objects.values_list("telegram_id", flat=True),
    )


AUTOPAYOUT_KEYS = (
    "autopayout_enabled",
    "autopayout_threshold",
    "autopayout_check_min",
    "autopayout_cooldown_min",
)


def _autopayout_env_defaults():
    enabled_raw = getattr(
        settings,
        "PLATEGA_AUTOPAYOUT_ENABLED",
        False,
    )
    threshold_raw = getattr(
        settings,
        "PLATEGA_AUTOPAYOUT_THRESHOLD_RUB",
        10000,
    )
    check_raw = getattr(settings, "PLATEGA_AUTOPAYOUT_CHECK_MIN", 15)
    cooldown_raw = getattr(
        settings,
        "PLATEGA_AUTOPAYOUT_COOLDOWN_MIN",
        60,
    )
    return {
        "enabled": bool(enabled_raw),
        "threshold": int(threshold_raw),
        "check_min": int(check_raw),
        "cooldown_min": int(cooldown_raw),
    }


def get_autopayout_config():
    """Конфиг автовывода: значения из БД поверх env-дефолтов."""
    from shop.models import BillingSetting

    config = _autopayout_env_defaults()
    stored = dict(
        BillingSetting.objects.filter(key__in=AUTOPAYOUT_KEYS).values_list(
            "key",
            "value",
        ),
    )
    if stored.get("autopayout_enabled") in ("1", "0"):
        config["enabled"] = stored["autopayout_enabled"] == "1"

    for key, name in (
        ("autopayout_threshold", "threshold"),
        ("autopayout_check_min", "check_min"),
        ("autopayout_cooldown_min", "cooldown_min"),
    ):
        if stored.get(key) not in (None, ""):
            try:
                config[name] = int(stored[key])
            except (TypeError, ValueError):
                pass

    return config


def save_autopayout_config(data):
    """Проверка и сохранение настроек автовывода.

    Возвращает (config, error).
    """
    enabled = str(data.get("enabled", "")).strip().lower() in (
        "1",
        "true",
        "on",
        "yes",
    )
    try:
        threshold = int(data.get("threshold", 0))
        check_min = int(data.get("check_min", 0))
        cooldown_min = int(data.get("cooldown_min", 0))
    except (TypeError, ValueError):
        return None, "Некорректные числа"

    payout_min = int(getattr(settings, "PLATEGA_PAYOUT_MIN", 1000))
    if threshold < payout_min or threshold > 100000000:
        return None, f"Порог — от {payout_min} ₽"

    if check_min < 1 or check_min > 1440:
        return None, "Проверка — от 1 до 1440 минут"

    if cooldown_min < 0 or cooldown_min > 2880:
        return None, "Пауза — от 0 до 2880 минут"

    from shop.models import BillingSetting

    for key, value in (
        ("autopayout_enabled", "1" if enabled else "0"),
        ("autopayout_threshold", str(threshold)),
        ("autopayout_check_min", str(check_min)),
        ("autopayout_cooldown_min", str(cooldown_min)),
    ):
        BillingSetting.objects.update_or_create(
            key=key,
            defaults={"value": value},
        )

    return get_autopayout_config(), None


def _fetch_open_rate():
    """USD->RUB из открытых источников: er-api, затем ЦБ РФ."""
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=8)
        rate = float((resp.json().get("rates") or {}).get("RUB") or 0)
        if 1 < rate < 10000:
            return rate, "er-api"
    except Exception as e:
        logger.warning("[billing] er-api rate failed: %s", e)

    try:
        resp = requests.get(
            "https://www.cbr-xml-daily.ru/daily_json.js",
            timeout=8,
        )
        valute = (resp.json().get("Valute") or {}).get("USD") or {}
        rate = float(valute.get("Value") or 0)
        if 1 < rate < 10000:
            return rate, "cbr"
    except Exception as e:
        logger.warning("[billing] cbr rate failed: %s", e)

    return 0.0, ""


def get_usd_rub_rate():
    """Актуальный курс USD->RUB для расчёта «вывести всё».

    Источники по приоритету: открытые (er-api, ЦБ), иначе настройка
    PLATEGA_USD_RUB_RATE. Возвращает (rate, source), кэш — 15 минут.
    """
    from django.core.cache import cache

    cached = cache.get(USD_RUB_RATE_CACHE_KEY)
    if cached:
        return cached

    rate, source = _fetch_open_rate()
    if not rate:
        rate = float(getattr(settings, "PLATEGA_USD_RUB_RATE", 80) or 80)
        source = "setting"

    result = (round(rate, 4), source)
    cache.set(USD_RUB_RATE_CACHE_KEY, result, USD_RUB_RATE_TTL)
    return result


def _fee_rate(channel):
    if channel == "card":
        return float(getattr(settings, "YOOMONEY_FEE_RATE", 0.03))

    return float(getattr(settings, "PLATEGA_FEE_RATE", 0.04))


def _channel_of(order):
    if order.payment_provider == "yoomoney":
        return "card"

    method = (order.payment_method or "").lower()
    if method == "sbp":
        return "sbp"

    if method == "crypto":
        return "crypto"

    return "platega_other"


def _empty_channel_totals():
    return {
        key: {"label": label, "gross": 0.0, "net": 0.0, "count": 0}
        for key, label, _provider in CHANNELS
    }


def _empty_day():
    return {
        "card": 0.0,
        "sbp": 0.0,
        "crypto": 0.0,
        "other": 0.0,
        "gross": 0.0,
        "refund": 0.0,
        "servers": 0.0,
        "ledger": 0.0,
    }


def prune_old_ledger_entries(days=31):
    """Удаление внеплановых записей старше days дней. Возвращает число."""
    from shop.models import LedgerEntry

    cutoff = timezone.now().date() - timedelta(days=days)
    deleted, _ = LedgerEntry.objects.filter(entry_date__lt=cutoff).delete()
    if deleted:
        logger.info("[billing] pruned %s old ledger entries", deleted)

    return deleted


def _next_expense_date(pay_day, today):
    """Ближайшее списание (сегодня или позже) для дня оплаты."""
    last_day = calendar.monthrange(today.year, today.month)[1]
    occ = date(today.year, today.month, min(pay_day, last_day))
    if occ >= today:
        return occ

    if today.month == 12:
        year, month = today.year + 1, 1
    else:
        year, month = today.year, today.month + 1

    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(pay_day, last_day))


def _server_expense_points(start, end):
    """Списания за сервера в [start, end]: {iso_date: сумма за день}.

    Месяц с ручной оплатой (last_paid внутри него): трата рисуется
    в день нажатия кнопки, авто-точка в этом месяце гаснет. Остальные
    месяцы — авто-списание в день оплаты.
    """
    points = {}
    for server in ServerExpense.objects.all():
        cost = float(server.monthly_cost or 0)
        if cost <= 0:
            continue

        manual = server.last_paid
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            if (
                manual is not None
                and manual.year == year
                and manual.month == month
            ):
                if start <= manual <= end:
                    iso = manual.isoformat()
                    points[iso] = round(points.get(iso, 0.0) + cost, 2)
            else:
                last_day = calendar.monthrange(year, month)[1]
                occ = date(year, month, min(server.pay_day, last_day))
                if start <= occ <= end:
                    iso = occ.isoformat()
                    points[iso] = round(points.get(iso, 0.0) + cost, 2)

            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1

    return points


def get_billing_stats(days=30, date_from=None, date_to=None):
    """Доходы по TOPUP PAID за период + за всё время + дневной график.

    Период — либо последние `days` дней, либо произвольный диапазон
    date_from..date_to. На график дополнительно ложатся списания за
    сервера; если диапазон включает сегодня — график продлевается до
    ближайших предстоящих списаний.
    """
    from shop.models import Order

    now = timezone.now()
    today = now.date()
    tz = timezone.get_current_timezone()

    custom = bool(date_from and date_to and date_from <= date_to)
    if custom:
        start_date = date_from
        end_date = min(date_to, today + timedelta(days=45))
        if (end_date - start_date).days > 366:
            end_date = start_date + timedelta(days=366)

        since = timezone.make_aware(
            datetime.combine(start_date, dt_time.min),
            tz,
        )
        # Итоги периода дальше сегодня не считаем.
        period_end = timezone.make_aware(
            datetime.combine(min(date_to, today), dt_time.max),
            tz,
        )
        days = 0
    else:
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 30

        days = max(1, min(days, 365))
        since = now - timedelta(days=days)
        start_date = since.date()
        end_date = today
        period_end = now

    # Предстоящие списания за сервера: диапазон включает сегодня —
    # продлеваем график до самого дальнего из ближайших списаний.
    if end_date >= today:
        upcoming = [
            _next_expense_date(server.pay_day, today)
            for server in ServerExpense.objects.all()
        ]
        if upcoming:
            end_date = max(
                end_date,
                min(max(upcoming), today + timedelta(days=45)),
            )

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    excluded = get_blacklisted_ids()

    def _income_qs(**kwargs):
        return Order.objects.filter(
            order_type="TOPUP",
            status="PAID",
            **kwargs,
        ).exclude(telegram_id__in=excluded)

    period_qs = _income_qs(
        created_at__gte=since,
        created_at__lte=period_end,
    ).only(
        "payment_provider",
        "payment_method",
        "amount",
        "created_at",
    )
    month_qs = _income_qs(created_at__gte=month_start).only(
        "payment_provider",
        "payment_method",
        "amount",
    )
    all_qs = _income_qs().only(
        "payment_provider",
        "payment_method",
        "amount",
    )

    def aggregate(orders):
        totals = _empty_channel_totals()
        for order in orders:
            channel = _channel_of(order)
            amount = float(order.amount or 0)
            totals[channel]["gross"] += amount
            totals[channel]["net"] += amount * (1 - _fee_rate(channel))
            totals[channel]["count"] += 1

        for item in totals.values():
            item["gross"] = round(item["gross"], 2)
            item["net"] = round(item["net"], 2)

        gross = round(sum(v["gross"] for v in totals.values()), 2)
        net = round(sum(v["net"] for v in totals.values()), 2)
        count = sum(v["count"] for v in totals.values())
        return {"channels": totals, "gross": gross, "net": net, "count": count}

    # Дневной график: чистыми и брутто по дням + возвраты + сервера
    timeline = []
    day_totals = {}

    def _day_entry(day):
        return day_totals.setdefault(day, _empty_day())

    for order in period_qs:
        day = order.created_at.date().isoformat()
        amount = float(order.amount or 0)
        entry = _day_entry(day)
        channel = _channel_of(order)
        key = channel if channel in ("card", "sbp", "crypto") else "other"
        entry[key] += round(amount * (1 - _fee_rate(channel)), 2)
        entry["gross"] += round(amount, 2)

    refund_qs = (
        Order.objects.filter(
            order_type="TOPUP",
            status__in=("REFUNDED", "CHARGEBACK"),
            created_at__gte=since,
            created_at__lte=period_end,
        )
        .exclude(telegram_id__in=excluded)
        .only("amount", "created_at")
    )
    refunds_total = 0.0
    for order in refund_qs:
        amount = round(float(order.amount or 0), 2)
        refunds_total += amount
        _day_entry(order.created_at.date().isoformat())["refund"] += amount

    refunds_total = round(refunds_total, 2)

    # Расходы — вниз: серверы лежат отрицательными, как внеплановые
    # траты. Доходы (прибыль/оборот) — вверх.
    for iso, cost in _server_expense_points(start_date, end_date).items():
        _day_entry(iso)["servers"] -= cost

    from shop.models import LedgerEntry

    for entry in LedgerEntry.objects.filter(
        entry_date__gte=start_date,
        entry_date__lte=end_date,
    ).only("amount", "entry_date"):
        _day_entry(entry.entry_date.isoformat())["ledger"] += round(
            float(entry.amount or 0),
            2,
        )

    cursor = start_date
    while cursor <= end_date:
        iso = cursor.isoformat()
        day = day_totals.get(iso, _empty_day())
        timeline.append(
            {
                "date": iso,
                "card": day["card"],
                "sbp": day["sbp"],
                "crypto": day["crypto"],
                "other": day["other"],
                "total": round(
                    day["card"] + day["sbp"] + day["crypto"] + day["other"],
                    2,
                ),
                "gross": day["gross"],
                "refund": day["refund"],
                "servers": day["servers"],
                "ledger": day["ledger"],
            },
        )
        cursor += timedelta(days=1)

    period = aggregate(period_qs)
    period["refunds"] = refunds_total
    period["ledger"] = round(sum(p["ledger"] for p in timeline), 2)

    if custom:
        yoomoney = get_yoomoney_block(date_from=date_from, date_to=date_to)
    else:
        yoomoney = get_yoomoney_block(days=days)

    wallet_daily = yoomoney.get("daily") or {}
    for point in timeline:
        point["wallet"] = wallet_daily.get(point["date"], 0.0)

    return {
        "days": days,
        "date_from": start_date.isoformat(),
        "date_to": end_date.isoformat(),
        "period": period,
        "month": aggregate(month_qs),
        "all_time": aggregate(all_qs),
        "timeline": timeline,
        "top_payers": get_top_payers(limit=50),
        "yoomoney": {
            "balance": yoomoney.get("balance"),
            "account_masked": yoomoney.get("account_masked"),
            "error": yoomoney.get("error", False),
            "total": yoomoney.get("total", 0.0),
        },
    }


def get_top_payers(limit=10):
    """Кто сколько принёс за всё время: id, имя, аватар, сумма, число."""
    from shop.models import Order
    from user.models import Profile

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10

    limit = max(1, min(limit, 50))

    rows = (
        Order.objects.filter(order_type="TOPUP", status="PAID")
        .exclude(telegram_id__in=get_blacklisted_ids())
        .values("telegram_id")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")[:limit]
    )
    if not rows:
        return []

    profiles = {
        p.telegram_id: p
        for p in Profile.objects.filter(
            telegram_id__in=[r["telegram_id"] for r in rows],
        ).only("telegram_id", "telegram_username", "telegram_avatar_url")
    }
    payers = []
    for row in rows:
        profile = profiles.get(row["telegram_id"])
        payers.append(
            {
                "telegram_id": row["telegram_id"],
                "username": (profile.telegram_username if profile else None),
                "avatar_url": (
                    profile.telegram_avatar_url if profile else None
                ),
                "total": float(row["total"] or 0),
                "count": row["count"],
            },
        )

    return payers


def get_ledger_data():
    """Разовые записи текущего месяца и их итог (знаковые суммы)."""
    from shop.models import LedgerEntry

    today = timezone.now().date()
    entries = LedgerEntry.objects.filter(
        entry_date__year=today.year,
        entry_date__month=today.month,
    )
    items = [
        {
            "id": e.id,
            "name": e.name,
            "amount": float(e.amount or 0),
            "entry_date": e.entry_date.isoformat(),
        }
        for e in entries
    ]
    total = round(sum(i["amount"] for i in items), 2)
    return {"entries": items, "total": total}


def get_servers_data():
    """Сервера + итоги; profit месяца считает вызывающий код."""
    today = timezone.now().date()
    items = []
    monthly_total = Decimal("0.00")
    for server in ServerExpense.objects.all():
        monthly_total += server.monthly_cost or Decimal("0.00")
        paid = (
            server.last_paid is not None
            and server.last_paid.year == today.year
            and server.last_paid.month == today.month
        )
        # Авто-оплата: день оплаты наступил, а кнопку не нажимали —
        # сервер считается оплаченным сам по себе (last_paid не трогаем:
        # там только ручные отметки).
        auto_paid = not paid and today.day >= server.pay_day
        items.append(
            {
                "id": server.id,
                "name": server.name,
                "monthly_cost": float(server.monthly_cost or 0),
                "pay_day": server.pay_day,
                "last_paid": (
                    server.last_paid.isoformat() if server.last_paid else None
                ),
                "paid_this_month": paid,
                "auto_paid": auto_paid,
                "overdue": (
                    today.day > server.pay_day and not paid and not auto_paid
                ),
            },
        )

    return {"servers": items, "monthly_total": float(monthly_total)}
