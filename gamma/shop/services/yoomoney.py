from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import transaction
from yoomoney import Client as YooClient
from yoomoney import Quickpay

from shop.models import Order


def create_payment_url(order_id, amount, receiver, success_url):
    quickpay = Quickpay(
        receiver=receiver,
        quickpay_form="shop",
        targets="Пополнение баланса Gamma VPN",
        paymentType="AC",
        sum=float(amount),
        label=str(order_id),
        successURL=success_url,
    )
    return quickpay.base_url


def verify_payment_api(order_id, expected_amount):
    """Проверяет платеж через YooMoney API (operation_history)."""
    token = getattr(settings, "YOOMONEY_TOKEN", "")
    if not token:
        return False
    try:
        client = YooClient(token)
        history = client.operation_history(
            label=str(order_id), type="deposition",
        )
        for op in history.operations:
            if op.status == "success" and op.amount >= float(expected_amount):
                return True
        return False
    except Exception:
        return False


def cancel_expired_orders():
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.ORDER_TIMEOUT_MINUTES,
    )
    return Order.objects.filter(
        status="PENDING",
        created_at__lt=cutoff,
    ).update(status="FAILED")


@transaction.atomic
def process_successful_payment(order_id):
    order = (
        Order.objects.select_for_update()
        .filter(id=order_id, status="PENDING")
        .first()
    )
    if not order:
        return None

    from datetime import timezone

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.ORDER_TIMEOUT_MINUTES,
    )
    if order.created_at < cutoff:
        order.status = "FAILED"
        order.save(update_fields=["status"])
        return None

    order.status = "PAID"
    order.save(update_fields=["status"])

    from user.models import Profile

    profile = Profile.objects.select_for_update().get(
        telegram_id=order.telegram_id,
    )
    profile.balance += order.amount
    profile.save(update_fields=["balance"])

    return order
