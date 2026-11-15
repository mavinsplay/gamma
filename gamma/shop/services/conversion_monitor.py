"""Compare persisted USDT balance snapshots every twelve hours."""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from shop.models import AdminNotification, BillingSetting
from shop.services.platega import get_platega_balances

__all__ = ["check_conversions", "read_usdt_balance"]

logger = logging.getLogger(__name__)
STATE_KEY = "platega_conversion_monitor"
CHECK_INTERVAL = timedelta(hours=12)
STATE_VERSION = 2


def read_usdt_balance():
    """Total USDT includes pending payouts; unfreezing is not income."""
    balances, error = get_platega_balances()
    if error:
        raise ValueError(f"Platega balance unavailable: {error}")

    if not isinstance(balances, list):
        raise ValueError("Invalid Platega balances response")

    entries = [
        entry
        for entry in balances
        if isinstance(entry, dict)
        and str(entry.get("currency", "")).upper() == "USDT"
    ]
    if len(entries) != 1:
        raise ValueError("Expected exactly one USDT balance")

    try:
        amount = Decimal(str(entries[0]["amount"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid USDT amount") from None

    if not amount.is_finite() or amount < 0:
        raise ValueError("Invalid USDT amount")

    return amount


def _load_state():
    value = (
        BillingSetting.objects.filter(key=STATE_KEY)
        .values_list(
            "value",
            flat=True,
        )
        .first()
    )
    state = json.loads(value) if value else {}
    # The old table parser's state/errors must not delay initialization.
    return state if state.get("version") == STATE_VERSION else {}


@transaction.atomic
def _record_balance(amount, checked_at):
    row, _ = BillingSetting.objects.get_or_create(key=STATE_KEY)
    row = BillingSetting.objects.select_for_update().get(pk=row.pk)
    state = json.loads(row.value) if row.value else {}
    if state.get("version") == STATE_VERSION and state.get("checked_at"):
        if checked_at <= datetime.fromisoformat(state["checked_at"]):
            return

        previous = Decimal(state["usdt_balance"])
        delta = amount - previous
        if delta > 0:
            AdminNotification.objects.get_or_create(
                event_key=f"conversion-balance:{checked_at.isoformat()}",
                defaults={
                    "text": (
                        "💵 Platega: баланс USDT увеличился\n"
                        f"Прирост баланса: <b>+{delta:.2f} USDT</b>\n"
                        f"Было: {previous:.2f} USDT\n"
                        f"Стало: {amount:.2f} USDT\n"
                        "Расчёт по разнице балансов между проверками. "
                        "Завершённые выводы за этот период уменьшают разницу."
                    ),
                },
            )

    row.value = json.dumps(
        {
            "version": STATE_VERSION,
            "usdt_balance": str(amount),
            "checked_at": checked_at.isoformat(),
            "next_check": (checked_at + CHECK_INTERVAL).isoformat(),
        },
    )
    row.save(update_fields=["value", "updated_at"])
    # Drop unsent obsolete warnings now that balance reading has recovered.
    AdminNotification.objects.filter(
        event_key__startswith="conversion-monitor-error:",
        sent_at__isnull=True,
    ).delete()


@transaction.atomic
def _record_failure(checked_at):
    row, _ = BillingSetting.objects.get_or_create(key=STATE_KEY)
    row = BillingSetting.objects.select_for_update().get(pk=row.pk)
    state = json.loads(row.value) if row.value else {}
    if state.get("version") != STATE_VERSION:
        state = {"version": STATE_VERSION}

    state["next_check"] = (checked_at + timedelta(hours=1)).isoformat()
    row.value = json.dumps(state)
    row.save(update_fields=["value", "updated_at"])
    AdminNotification.objects.get_or_create(
        event_key=f"conversion-monitor-error:{checked_at.date()}",
        defaults={
            "text": (
                "⚠️ Не удалось получить баланс USDT через API Platega. "
                "Сохранённый баланс не изменён. Повтор через час."
            ),
        },
    )


async def check_conversions():
    if not (
        settings.ADMIN_TELEGRAM_ID
        and settings.PLATEGA_MERCHANT_ID
        and settings.PLATEGA_SECRET
    ):
        return

    state = await sync_to_async(_load_state)()
    now = timezone.now()
    if state.get("next_check") and now < datetime.fromisoformat(
        state["next_check"],
    ):
        return

    try:
        amount = await sync_to_async(read_usdt_balance)()
    except Exception as error:
        logger.warning("USDT balance check failed (%s)", type(error).__name__)
        await sync_to_async(_record_failure)(now)
        return

    await sync_to_async(_record_balance)(amount, timezone.now())
