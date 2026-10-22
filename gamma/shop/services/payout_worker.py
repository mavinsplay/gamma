"""Исполнитель заявок на вывод для фоновой задачи бота.

Всё, что трогает БД — синхронные функции (бот вызывает их через
sync_to_async). Сам браузер — асинхронный, выполняется в loop бота.
"""

from datetime import timedelta
import logging

from django.conf import settings
from django.utils import timezone

from shop.models import Order, PayoutJob
from shop.services.billing import get_usd_rub_rate
from shop.services.platega import get_platega_balances
from shop.services.platega_ui import (
    compute_withdraw_all,
    configured_last4,
    run_ui_card_payout,
    should_autopayout,
    ui_payout_configured,
    UiPayoutError,
)

logger = logging.getLogger(__name__)

__all__ = [
    "active_job_exists",
    "claim_next_job",
    "execute_job",
    "process_payout_queue",
    "recent_payout_exists",
    "schedule_auto_job",
]


def claim_next_job():
    """Старейшая заявка из очереди -> RUNNING. None, если пусто."""
    job = (
        PayoutJob.objects.filter(status=PayoutJob.STATUS_QUEUED)
        .order_by("created_at")
        .first()
    )
    if job is None:
        return None

    job.status = PayoutJob.STATUS_RUNNING
    job.save(update_fields=["status", "updated_at"])
    return job


def active_job_exists():
    """Есть ли незавершённый вывод (защита от дабл-клика)."""
    return PayoutJob.objects.filter(
        status__in=(PayoutJob.STATUS_QUEUED, PayoutJob.STATUS_RUNNING),
    ).exists()


def recent_payout_exists(minutes):
    """Был ли успешный вывод за последние minutes (аудит + задачи)."""
    since = timezone.now() - timedelta(minutes=minutes)
    if Order.objects.filter(
        order_type="PAYOUT",
        status="PAID",
        created_at__gte=since,
    ).exists():
        return True

    return PayoutJob.objects.filter(
        status=PayoutJob.STATUS_DONE,
        updated_at__gte=since,
    ).exists()


def get_withdrawable_rub():
    """Доступное к выводу в рублях: USDT доступно × живой курс.

    В amount Platega кладёт итог вместе с «в процессе выплаты»,
    для вывода считаем только доступный остаток (amount − заморозка).
    RUB-баланс — это деньги НА холде, для вывода не считаем.
    Возвращает (amount, error).
    """
    balances, error = get_platega_balances()
    if not isinstance(balances, list):
        return 0.0, error or "api_error"

    from shop.services.billing import parse_usdt_balance

    available, _in_process, _total = parse_usdt_balance(balances)
    rate, _source = get_usd_rub_rate()
    return round(available * rate, 2), None


def schedule_auto_job():
    """Создать авто-заявку, если порог достигнут. Иначе None."""
    from shop.services.billing import get_autopayout_config

    config = get_autopayout_config()
    if not config["enabled"]:
        return None

    if not ui_payout_configured():
        return None

    if active_job_exists():
        return None

    if recent_payout_exists(config["cooldown_min"]):
        return None

    balance, error = get_withdrawable_rub()
    if error:
        logger.warning("[payout-worker] balance check failed: %s", error)
        return None

    payout_min = int(getattr(settings, "PLATEGA_PAYOUT_MIN", 1000))
    if not should_autopayout(balance, config["threshold"], payout_min):
        return None

    usd_rate, _usd_source = get_usd_rub_rate()
    amount = compute_withdraw_all(
        balance,
        fee_usd=float(getattr(settings, "PLATEGA_PAYOUT_FEE_USD", 0.5)),
        usd_rub_rate=usd_rate,
        payout_min=payout_min,
        payout_max=int(getattr(settings, "PLATEGA_PAYOUT_MAX", 87500)),
    )
    if not amount:
        return None

    job = PayoutJob.objects.create(
        amount=amount,
        is_max=True,
        dest_last4=configured_last4(),
        mode=PayoutJob.MODE_AUTO,
    )
    logger.warning(
        "[payout-worker] auto job #%s amount=%s (balance=%s)",
        job.id,
        amount,
        balance,
    )
    return job


async def _notify(bot, admin_id, text, photo_path=None):
    if not bot or not admin_id:
        return

    try:
        if photo_path:
            from aiogram.types import FSInputFile

            await bot.send_photo(
                admin_id,
                FSInputFile(photo_path),
                caption=text,
            )
        else:
            await bot.send_message(admin_id, text)
    except Exception as e:
        logger.error("[payout-worker] notify failed: %s", e)


async def execute_job(bot, admin_id, job):
    """Выполнить заявку в браузере, записать итог, уведомить админа."""
    from asgiref.sync import sync_to_async

    dest = f"**** {job.dest_last4}" if job.dest_last4 else "карта"
    mode = "авто" if job.mode == PayoutJob.MODE_AUTO else "вручную"
    requested = f"{job.amount} ₽" if job.amount else "максимума"
    try:
        result = await run_ui_card_payout(float(job.amount), is_max=job.is_max)
    except UiPayoutError as e:
        job.status = PayoutJob.STATUS_FAILED
        job.error = str(e)[:500]
        await sync_to_async(job.save)(
            update_fields=["status", "error", "updated_at"],
        )
        logger.error("[payout-worker] job #%s failed: %s", job.id, job.error)
        await _notify(
            bot,
            admin_id,
            f"❌ Вывод {requested} на {dest} ({mode}) не удался: "
            f"{job.error}",
            photo_path=e.screenshot,
        )
        return job

    # Сайт мог принять уменьшенную сумму (кнопка была disabled) —
    # в аудите и уведомлениях отражаем факт.
    from decimal import Decimal

    actual = (result or {}).get("actual_amount_rub") or float(job.amount)
    job.amount = Decimal(str(actual))
    job.status = PayoutJob.STATUS_DONE
    job.result = result
    await sync_to_async(job.save)(
        update_fields=["amount", "status", "result", "updated_at"],
    )

    def _audit():
        Order.objects.create(
            tariff=None,
            telegram_id=admin_id,
            amount=job.amount,
            order_type="PAYOUT",
            status="PAID",
            payment_provider="platega",
            platega_transaction_id="",
        )

    await sync_to_async(_audit)()
    logger.warning(
        "[payout-worker] job #%s done amount=%s",
        job.id,
        job.amount,
    )
    shots = (result or {}).get("shots") or []
    photo = None
    if shots:
        from pathlib import Path

        profile = Path(
            getattr(settings, "PLATEGA_UI_PROFILE_DIR", "./platega_profile"),
        )
        candidate = profile / "screenshots" / f"{shots[-1]}.png"
        if candidate.exists():
            photo = str(candidate)

    page_text = (result or {}).get("page_text") or ""
    await _notify(
        bot,
        admin_id,
        f"✅ Вывод {job.amount} ₽ на {dest} ({mode}) выполнен. {page_text}",
        photo_path=photo,
    )
    return job


async def process_payout_queue(bot, admin_id, check_auto=True):
    """Один тик воркера: очередь всегда, автопорог — по флагу."""
    from asgiref.sync import sync_to_async

    if not ui_payout_configured():
        return

    job = await sync_to_async(claim_next_job)()
    if job is not None:
        await execute_job(bot, admin_id, job)
        return

    if not check_auto:
        return

    auto_job = await sync_to_async(schedule_auto_job)()
    if auto_job is not None:
        await execute_job(bot, admin_id, auto_job)
