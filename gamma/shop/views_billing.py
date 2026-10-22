"""Админская билинг-панель: балансы, статистика, сервера, вывод."""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone

from shop.models import (
    ExcludedPayer,
    LedgerEntry,
    Order,
    PayoutJob,
    ServerExpense,
)
from shop.services.billing import (
    get_billing_stats,
    get_blacklisted_ids,
    get_ledger_data,
    get_servers_data,
    get_usd_rub_rate,
    parse_usdt_balance,
    prune_old_ledger_entries,
)
from shop.services.payout_worker import active_job_exists
from shop.services.platega import (
    create_card_payout,
    get_payout_cards,
    get_platega_balances,
)
from shop.services.platega_ui import (
    compute_withdraw_all,
    configured_last4,
    ui_payout_configured,
)
from shop.views import _get_authorized_telegram_id

logger = logging.getLogger(__name__)

__all__ = [
    "billing_api",
    "billing_server_api",
    "billing_payout_api",
    "billing_payout_job_api",
    "billing_autopayout_api",
    "billing_blacklist_api",
    "billing_ledger_api",
]

BALANCES_CACHE_KEY = "billing:balances"
BALANCES_TTL = 60


def _parse_iso_date(raw):
    try:
        return datetime.strptime((raw or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _usdt_amount(balances):
    """USDT доступное к выводу (без «в процессе выплаты»).

    /balance/all отдаёт в amount итог вместе с заявками в работе,
    кабинет показывает их отдельно. Доступно = amount − заморозка.
    """
    available, _in_process, _total = parse_usdt_balance(balances)
    return available


def _autopayout_payload():
    from shop.services.billing import get_autopayout_config

    config = get_autopayout_config()
    last = (
        PayoutJob.objects.filter(
            mode=PayoutJob.MODE_AUTO,
            status=PayoutJob.STATUS_DONE,
        )
        .order_by("-updated_at")
        .first()
    )
    config["last_amount"] = float(last.amount or 0) if last else None
    config["last_at"] = last.updated_at.isoformat() if last else None
    return config


def _require_admin(request):
    """Return admin telegram_id or None (auth + роль в одном месте)."""
    uid = _get_authorized_telegram_id(request)
    if uid is None:
        return None

    if str(uid) != str(settings.ADMIN_TELEGRAM_ID):
        logger.warning("Billing access denied for tg=%s", uid)
        return None

    try:
        return int(uid)
    except (TypeError, ValueError):
        return None


def billing_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    admin_id = _require_admin(request)
    if admin_id is None:
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        days = int(request.POST.get("days", 30))
    except (TypeError, ValueError):
        days = 30

    days = max(1, min(days, 365))

    date_from = _parse_iso_date(request.POST.get("date_from"))
    date_to = _parse_iso_date(request.POST.get("date_to"))
    custom_range = bool(date_from and date_to and date_from <= date_to)

    balances = cache.get(BALANCES_CACHE_KEY)
    balances_error = None
    if balances is None:
        balances, balances_error = get_platega_balances()
        if not isinstance(balances, list):
            balances, balances_error = None, balances_error or "api_error"
        else:
            cache.set(BALANCES_CACHE_KEY, balances, BALANCES_TTL)

    payout_secret = bool(getattr(settings, "PLATEGA_PAYOUT_SECRET", ""))
    payout_configured = payout_secret or ui_payout_configured()
    payout_mode = (
        "api" if payout_secret else ("ui" if ui_payout_configured() else "off")
    )
    payout_min = int(getattr(settings, "PLATEGA_PAYOUT_MIN", 1000))
    payout_max = int(getattr(settings, "PLATEGA_PAYOUT_MAX", 87500))
    payout_fee_usd = float(getattr(settings, "PLATEGA_PAYOUT_FEE_USD", 0.5))
    payout_cards = []
    # Сохранённые карты отдаёт только Payout API; в ui-режиме без
    # секрета не дёргаем (иначе шум "Payout secret is not configured").
    if payout_secret:
        cards, cards_error = get_payout_cards()
        if cards:
            # Только маскированные данные — PAN никогда не покидает Platega.
            payout_cards = [
                {
                    "cardId": c.get("cardId"),
                    "masked": c.get("masked"),
                    "brand": c.get("brand"),
                    "label": c.get("label"),
                    "status": c.get("status"),
                }
                for c in cards
                if c.get("cardId") and c.get("status") == "ACTIVE"
            ]
        elif cards_error and cards_error != "not_configured":
            logger.warning("Billing cards fetch failed: %s", cards_error)

    if custom_range:
        stats = get_billing_stats(date_from=date_from, date_to=date_to)
    else:
        stats = get_billing_stats(days=days)

    servers = get_servers_data()
    # Внеплановые старше месяца удаляются сами при открытии панели.
    prune_old_ledger_entries()
    ledger = get_ledger_data()
    month_profit = round(
        stats["month"]["net"] - servers["monthly_total"] + ledger["total"],
        2,
    )
    blacklisted = sorted(get_blacklisted_ids())

    preset_card_id = getattr(settings, "PLATEGA_PAYOUT_CARD_ID", "")
    usd_rate, usd_rate_source = get_usd_rub_rate()
    payout_all_amount = compute_withdraw_all(
        _usdt_amount(balances) * usd_rate,
        fee_usd=payout_fee_usd,
        usd_rub_rate=usd_rate,
        payout_min=payout_min,
        payout_max=payout_max,
    )
    dest_masked = None
    if payout_mode == "ui":
        last4 = configured_last4()
        dest_masked = f"**** {last4}" if last4 else None

    usdt_available, usdt_in_process, usdt_total = parse_usdt_balance(balances)
    return JsonResponse(
        {
            "success": True,
            "balances": balances,
            "balances_error": balances_error,
            "usdt_available": usdt_available,
            "usdt_in_process": usdt_in_process,
            "usdt_total": usdt_total,
            "payout_configured": payout_configured,
            "payout_mode": payout_mode,
            "payout_cards": payout_cards,
            "payout_preset_card_id": preset_card_id or None,
            "payout_min": payout_min,
            "payout_max": payout_max,
            "payout_fee_usd": payout_fee_usd,
            "payout_all_amount": payout_all_amount,
            "payout_dest_masked": dest_masked,
            "usd_rub_rate": usd_rate,
            "usd_rub_rate_source": usd_rate_source,
            "autopayout": _autopayout_payload(),
            "stats": stats,
            "servers": servers,
            "month_profit": month_profit,
            "blacklisted": blacklisted,
            "ledger": ledger,
        },
    )


def billing_blacklist_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    admin_id = _require_admin(request)
    if admin_id is None:
        return JsonResponse({"error": "Forbidden"}, status=403)

    action = request.POST.get("action", "")
    try:
        target_id = int(request.POST.get("telegram_id", 0))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Некорректный id"}, status=400)

    if target_id <= 0:
        return JsonResponse({"error": "Некорректный id"}, status=400)

    if action == "add":
        ExcludedPayer.objects.get_or_create(telegram_id=target_id)
    elif action == "remove":
        ExcludedPayer.objects.filter(telegram_id=target_id).delete()
    else:
        return JsonResponse({"error": "Invalid action"}, status=400)

    return JsonResponse(
        {
            "success": True,
            "blacklisted": sorted(get_blacklisted_ids()),
        },
    )


def billing_server_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    admin_id = _require_admin(request)
    if admin_id is None:
        return JsonResponse({"error": "Forbidden"}, status=403)

    action = request.POST.get("action", "")
    if action in ("create", "update"):
        name = (request.POST.get("name") or "").strip()[:100]
        if not name:
            return JsonResponse({"error": "Укажите название"}, status=400)

        try:
            monthly_cost = Decimal(str(request.POST.get("monthly_cost", 0)))
        except (TypeError, ValueError, InvalidOperation):
            return JsonResponse({"error": "Некорректная сумма"}, status=400)

        if monthly_cost <= 0 or monthly_cost > 10000000:
            return JsonResponse({"error": "Некорректная сумма"}, status=400)

        try:
            pay_day = int(request.POST.get("pay_day", 0))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Некорректный день"}, status=400)

        if pay_day < 1 or pay_day > 31:
            return JsonResponse(
                {"error": "День оплаты — число 1–31"},
                status=400,
            )

        if action == "create":
            server = ServerExpense(
                name=name,
                monthly_cost=monthly_cost,
                pay_day=pay_day,
            )
            try:
                server.full_clean()
            except ValidationError:
                return JsonResponse(
                    {"error": "Некорректные данные"},
                    status=400,
                )

            server.save()
        else:
            try:
                server_id = int(request.POST.get("id", 0))
            except (TypeError, ValueError):
                return JsonResponse({"error": "Некорректный id"}, status=400)

            server = ServerExpense.objects.filter(id=server_id).first()
            if not server:
                return JsonResponse({"error": "Не найдено"}, status=404)

            server.name = name
            server.monthly_cost = monthly_cost
            server.pay_day = pay_day
            try:
                server.full_clean()
            except ValidationError:
                return JsonResponse(
                    {"error": "Некорректные данные"},
                    status=400,
                )

            server.save()

        return JsonResponse({"success": True, "servers": get_servers_data()})

    if action == "delete":
        try:
            server_id = int(request.POST.get("id", 0))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Некорректный id"}, status=400)

        deleted, _ = ServerExpense.objects.filter(id=server_id).delete()
        if not deleted:
            return JsonResponse({"error": "Не найдено"}, status=404)

        return JsonResponse({"success": True, "servers": get_servers_data()})

    if action == "mark_paid":
        try:
            server_id = int(request.POST.get("id", 0))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Некорректный id"}, status=400)

        server = ServerExpense.objects.filter(id=server_id).first()
        if not server:
            return JsonResponse({"error": "Не найдено"}, status=404)

        server.last_paid = date.today()
        server.save(update_fields=["last_paid"])
        return JsonResponse({"success": True, "servers": get_servers_data()})

    return JsonResponse({"error": "Invalid action"}, status=400)


def billing_ledger_api(request):
    from datetime import datetime

    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    admin_id = _require_admin(request)
    if admin_id is None:
        return JsonResponse({"error": "Forbidden"}, status=403)

    action = request.POST.get("action", "")
    if action == "create":
        name = (request.POST.get("name") or "").strip()[:100]
        if not name:
            return JsonResponse({"error": "Укажите описание"}, status=400)

        try:
            amount = Decimal(str(request.POST.get("amount", 0)))
        except (TypeError, ValueError, InvalidOperation):
            return JsonResponse({"error": "Некорректная сумма"}, status=400)

        if amount == 0 or abs(amount) > 100000000:
            return JsonResponse({"error": "Некорректная сумма"}, status=400)

        entry_date_raw = (request.POST.get("entry_date") or "").strip()
        if entry_date_raw:
            try:
                entry_date = datetime.strptime(
                    entry_date_raw,
                    "%Y-%m-%d",
                ).date()
            except ValueError:
                return JsonResponse({"error": "Некорректная дата"}, status=400)
        else:
            entry_date = date.today()

        entry = LedgerEntry(
            name=name,
            amount=amount,
            entry_date=entry_date,
        )
        try:
            entry.full_clean()
        except ValidationError:
            return JsonResponse(
                {"error": "Некорректные данные"},
                status=400,
            )

        entry.save()
        return JsonResponse({"success": True, "ledger": get_ledger_data()})

    if action == "delete":
        try:
            entry_id = int(request.POST.get("id", 0))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Некорректный id"}, status=400)

        deleted, _ = LedgerEntry.objects.filter(id=entry_id).delete()
        if not deleted:
            return JsonResponse({"error": "Не найдено"}, status=404)

        return JsonResponse({"success": True, "ledger": get_ledger_data()})

    return JsonResponse({"error": "Invalid action"}, status=400)


def billing_payout_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    admin_id = _require_admin(request)
    if admin_id is None:
        return JsonResponse({"error": "Forbidden"}, status=403)

    payout_min = int(getattr(settings, "PLATEGA_PAYOUT_MIN", 1000))
    payout_max = int(getattr(settings, "PLATEGA_PAYOUT_MAX", 87500))

    is_max = str(request.POST.get("is_max", "")).strip() == "1"
    try:
        amount = int(request.POST.get("amount", 0))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Некорректная сумма"}, status=400)

    if not is_max and (amount < payout_min or amount > payout_max):
        return JsonResponse(
            {"error": f"Сумма вывода — от {payout_min} до {payout_max} ₽"},
            status=400,
        )

    if not getattr(settings, "PLATEGA_PAYOUT_SECRET", ""):
        # Payout API не одобрен — заявка в очередь браузерного вывода.
        if not ui_payout_configured():
            return JsonResponse(
                {"error": "Вывод не подключён (нет доступа к кабинету)"},
                status=400,
            )

        if active_job_exists():
            return JsonResponse(
                {"error": "Вывод уже выполняется. Дождитесь завершения."},
                status=429,
            )

        job = PayoutJob.objects.create(
            amount=amount if not is_max else 0,
            is_max=is_max,
            dest_last4=configured_last4(),
            mode=PayoutJob.MODE_MANUAL,
        )
        logger.warning(
            "Billing UI payout queued by tg=%s amount=%s job=%s",
            admin_id,
            amount,
            job.id,
        )
        return JsonResponse({"success": True, "mode": "ui", "job_id": job.id})

    # Защита от двойного клика: успешный вывод моложе минуты —
    # второй такой же запрос отклоняем (Idempotency-Key у Platega
    # свой на каждый запрос, от дабл-сабмита он не спасает).
    recent = Order.objects.filter(
        order_type="PAYOUT",
        status="PAID",
        telegram_id=admin_id,
        created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists()
    if recent:
        return JsonResponse(
            {"error": "Вывод уже выполняется. Подождите минуту."},
            status=429,
        )

    card_id = (request.POST.get("card_id") or "").strip()
    card_number = "".join(
        ch for ch in (request.POST.get("card_number") or "") if ch.isdigit()
    )
    if bool(card_id) == bool(card_number):
        return JsonResponse(
            {"error": "Укажите карту: сохранённая или номер"},
            status=400,
        )

    if card_id:
        # cardId принимаем только из живого списка активных карт —
        # нельзя подсунуть чужой идентификатор.
        cards, _ = get_payout_cards()
        active_ids = {
            c.get("cardId")
            for c in (cards or [])
            if c.get("status") == "ACTIVE"
        }
        if card_id not in active_ids:
            return JsonResponse({"error": "Карта не найдена"}, status=400)

    # В логах — только факт и сумма, никаких идентификаторов карт и PAN.
    logger.warning(
        "Billing payout requested by tg=%s amount=%s saved_card=%s",
        admin_id,
        amount,
        bool(card_id),
    )

    result, error = create_card_payout(
        amount_rub=amount,
        card_id=card_id or None,
        card_number=card_number or None,
    )
    if error or not isinstance(result, dict):
        return JsonResponse(
            {"error": "Platega отклонил вывод. Проверьте баланс."},
            status=502,
        )

    # Аудит: вывод фиксируем как заказ, в статистику доходов не попадает
    # (там считаются только TOPUP), PAN нигде не храним.
    Order.objects.create(
        tariff=None,
        telegram_id=admin_id,
        amount=amount,
        order_type="PAYOUT",
        status="PAID",
        payment_provider="platega",
        platega_transaction_id=str(result.get("withdrawalRecordId") or ""),
    )
    cache.delete(BALANCES_CACHE_KEY)

    return JsonResponse(
        {
            "success": True,
            "mode": "api",
            "status": result.get("status"),
            "card_masked": result.get("cardMasked"),
            "amount_usdt_debited": result.get("amountUsdtDebited"),
            "withdrawal_id": result.get("withdrawalRecordId"),
        },
    )


def billing_autopayout_api(request):
    """Сохранение настроек автовывода из панели."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    admin_id = _require_admin(request)
    if admin_id is None:
        return JsonResponse({"error": "Forbidden"}, status=403)

    from shop.services.billing import save_autopayout_config

    config, error = save_autopayout_config(request.POST)
    if error:
        return JsonResponse({"error": error}, status=400)

    logger.warning(
        "Billing autopayout updated by tg=%s: %s",
        admin_id,
        config,
    )
    return JsonResponse({"success": True, "autopayout": config})


def billing_payout_job_api(request):
    """Статус заявки браузерного вывода (опрос из панели)."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    admin_id = _require_admin(request)
    if admin_id is None:
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        job_id = int(request.POST.get("job_id", 0))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Некорректный id"}, status=400)

    job = PayoutJob.objects.filter(id=job_id).first()
    if not job:
        return JsonResponse({"error": "Не найдено"}, status=404)

    return JsonResponse(
        {
            "success": True,
            "status": job.status,
            "mode": job.mode,
            "amount": float(job.amount or 0),
            "dest_masked": (
                f"**** {job.dest_last4}" if job.dest_last4 else None
            ),
            "error": job.error or None,
            "page_text": (job.result or {}).get("page_text") or None,
        },
    )
