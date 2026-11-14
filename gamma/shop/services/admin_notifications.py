from datetime import timedelta
from html import escape
import logging
from urllib.parse import quote

from asgiref.sync import sync_to_async
from django.db.models import Q
from django.utils import timezone

from shop.models import AdminNotification

__all__ = ["queue_payment_notification", "send_pending_notifications"]

logger = logging.getLogger(__name__)


def queue_payment_notification(order, profile):
    username = (profile.telegram_username or "").lstrip("@")
    url = (
        f"https://t.me/{quote(username, safe='')}"
        if username
        else f"tg://user?id={profile.telegram_id}"
    )
    label = escape(f"@{username}" if username else str(profile.telegram_id))
    text = (
        f"💰 Поступил платёж: <b>{order.amount:.2f} ₽</b>\n"
        f'Пользователь: <a href="{escape(url, quote=True)}">{label}</a>\n'
        f"Telegram ID: <code>{profile.telegram_id}</code>\n"
        f"Заказ №{order.pk} · {escape(order.get_payment_provider_display())}"
    )
    if order.payment_method:
        text += f" · {escape(order.get_payment_method_display())}"

    if order.tariff:
        text += f"\nТариф: {escape(order.tariff.name)}"

    if order.order_type == "TOPUP":
        text += "\nПополнение баланса для оплаты услуг."

    AdminNotification.objects.get_or_create(
        event_key=f"payment:{order.pk}",
        defaults={"text": text},
    )


def _pending_notifications():
    return list(
        AdminNotification.objects.filter(sent_at__isnull=True)
        .filter(Q(retry_at__isnull=True) | Q(retry_at__lte=timezone.now()))
        .order_by("pk")[:20],
    )


async def send_pending_notifications(bot, admin_id):
    if not admin_id:
        return

    for notification in await sync_to_async(_pending_notifications)():
        try:
            await bot.send_message(
                admin_id,
                notification.text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as error:
            # Do not log Telegram URLs containing the bot token.
            logger.warning(
                "Admin notification %s failed (%s)",
                notification.pk,
                type(error).__name__,
            )
            await sync_to_async(
                AdminNotification.objects.filter(pk=notification.pk).update,
            )(retry_at=timezone.now() + timedelta(minutes=5))
        else:
            await sync_to_async(
                AdminNotification.objects.filter(pk=notification.pk).update,
            )(sent_at=timezone.now(), retry_at=None)
