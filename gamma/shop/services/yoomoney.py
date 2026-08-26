from datetime import datetime, timedelta, timezone
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from yoomoney import Client as YooClient
from yoomoney import Quickpay

from shop.models import Order

logger = logging.getLogger(__name__)

__all__ = [
    "create_payment_url",
    "verify_payment_api",
    "verify_operation",
    "cancel_expired_orders",
    "process_successful_payment",
]


def create_payment_url(order_id, amount, receiver, success_url):
    quickpay = Quickpay(
        receiver=receiver,
        quickpay_form="shop",
        targets="Пополнение баланса Gamma",
        paymentType="AC",
        sum=float(amount),
        label=str(order_id),
        successURL=success_url,
    )
    return quickpay.base_url


def verify_payment_api(order_id, expected_amount):
    min_amount = float(expected_amount) * 0.95
    token = getattr(settings, "YOOMONEY_TOKEN", "")
    if not token:
        logger.error("[yoomoney] No token configured")
        return False

    try:
        client = YooClient(token)

        label_history = client.operation_history(
            label=str(order_id),
            records=5,
        )
        for op in label_history.operations:
            if op.status == "success" and op.amount >= min_amount:
                return True

        recent = client.operation_history(
            records=50,
            type="deposition",
        )
        for op in recent.operations:
            if (
                op.status == "success"
                and op.amount >= min_amount
                and str(op.label) == str(order_id)
            ):
                return True

        return False
    except Exception as e:
        logger.error(f"[yoomoney] verify_payment_api error: {e}")
        return False


def verify_operation(
    operation_id,
    expected_order_id,
    expected_amount,
):
    token = getattr(settings, "YOOMONEY_TOKEN", "")
    if not token:
        logger.error("[yoomoney] No token configured")
        return False

    try:
        client = YooClient(token)
        details = client.operation_details(operation_id)
        logger.info(
            f"[yoomoney] verify_operation: id={operation_id} "
            f"status={details.status} amount={details.amount} "
            f"label={details.label}",
        )
        if details.status != "success":
            return False

        if details.amount < float(expected_amount) * 0.95:
            return False

        if str(details.label) != str(expected_order_id):
            return False

        return True
    except Exception as e:
        logger.error(f"[yoomoney] verify_operation error: {e}")
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
        .filter(id=order_id)
        .exclude(status="PAID")
        .first()
    )
    if not order:
        return None

    from user.models import Profile

    profile = (
        Profile.objects.select_for_update()
        .filter(
            telegram_id=order.telegram_id,
        )
        .first()
    )
    if not profile:
        return None

    order.status = "PAID"
    order.save(update_fields=["status"])

    profile.balance += order.amount
    profile.save(update_fields=["balance"])

    cache.delete(f"sync_data:{order.telegram_id}")

    return order
