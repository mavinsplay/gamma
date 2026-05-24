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
    """Проверяет платеж через YooMoney API.

    Сначала ищет по label (самый точный способ).
    Если не нашло — ищет среди последних 50 операций без фильтра.
    """
    import sys

    token = getattr(settings, "YOOMONEY_TOKEN", "")
    if not token:
        print("[yoomoney] No token configured", file=sys.stderr)
        return False
    try:
        client = YooClient(token)

        # 1 — поиск по label (точное совпадение)
        label_history = client.operation_history(
            label=str(order_id), records=5,
        )
        for op in label_history.operations:
            if op.status == "success" and op.amount >= float(expected_amount):
                return True

        # 2 — широкий поиск среди последних операций
        recent = client.operation_history(records=50, type="deposition")
        for op in recent.operations:
            if (
                op.status == "success"
                and op.amount >= float(expected_amount)
                and str(op.label) == str(order_id)
            ):
                return True

        return False
    except Exception as e:
        print(
            f"[yoomoney] verify_payment_api error: {e}",
            file=sys.stderr,
        )
        return False


def verify_operation(operation_id, expected_order_id, expected_amount):
    """Проверяет конкретную операцию через YooMoney API (operation_details).

    Вызывается при редиректе с ЮMoney — у нас есть operation_id из URL.
    """
    import sys

    token = getattr(settings, "YOOMONEY_TOKEN", "")
    if not token:
        print("[yoomoney] No token configured", file=sys.stderr)
        return False
    try:
        client = YooClient(token)
        details = client.operation_details(operation_id)
        print(
            f"[yoomoney] verify_operation: id={operation_id} "
            f"status={details.status} amount={details.amount} "
            f"label={details.label}",
            file=sys.stderr,
        )
        if details.status != "success":
            return False
        if details.amount < float(expected_amount):
            return False
        if str(details.label) != str(expected_order_id):
            return False
        return True
    except Exception as e:
        print(
            f"[yoomoney] verify_operation error: {e}",
            file=sys.stderr,
        )
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
