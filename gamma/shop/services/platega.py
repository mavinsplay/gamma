import logging

from django.conf import settings
from django.db import transaction

from shop.platega import Platega, PlategaAPIError

logger = logging.getLogger(__name__)

__all__ = [
    "create_platega_payment",
    "verify_platega_payment",
    "process_platega_callback",
]


def _get_client():
    merchant_id = getattr(settings, "PLATEGA_MERCHANT_ID", "")
    secret = getattr(settings, "PLATEGA_SECRET", "")
    if not merchant_id or not secret:
        raise ValueError(
            "Platega is not configured (PLATEGA_MERCHANT_ID / PLATEGA_SECRET)",
        )

    return Platega(merchant_id, secret)


def create_platega_payment(
    order_id,
    amount,
    payment_method,
    return_url,
    failed_url,
):
    """
    Create a Platega transaction and return (redirect_url, transaction_id).

    Args:
        order_id: Internal Order.id — stored as payload for callback matching
        amount: Decimal amount in RUB
        payment_method: Platega.METHOD_SBP_QR or Platega.METHOD_CRYPTO
        return_url: Success redirect URL
        failed_url: Failure redirect URL

    Returns:
        tuple(str, str): (redirect_url, platega_transaction_id)

    Raises:
        PlategaAPIError: on API failure
        ValueError: if credentials not configured
    """
    client = _get_client()
    result = client.create_payment(
        amount=float(amount),
        currency="RUB",
        payment_method=payment_method,
        description=f"Пополнение баланса Gamma (заказ #{order_id})",
        return_url=return_url,
        failed_url=failed_url,
        payload=str(order_id),
    )
    redirect_url = result.get("redirect", "")
    transaction_id = result.get("transactionId", "")
    return redirect_url, transaction_id


def verify_platega_payment(transaction_id):
    """
    Check payment status by Platega transaction ID.

    Returns:
        str: Platega status ("CONFIRMED", "CANCELED",
             "CHARGEBACKED", "PENDING") or None on error.
    """
    if not transaction_id:
        return None

    try:
        client = _get_client()
        result = client.get_payment_status(transaction_id)
        return result.get("status")
    except PlategaAPIError as e:
        logger.error(f"[platega] verify_platega_payment error: {e}")
        return None
    except ValueError as e:
        logger.error(f"[platega] verify_platega_payment config error: {e}")
        return None
    except Exception as e:
        logger.error(f"[platega] verify_platega_payment unexpected error: {e}")
        return None


@transaction.atomic
def process_platega_callback(order_id, status):
    """
    Process a Platega callback for a given order.

    Handles CONFIRMED → PAID, CANCELED → FAILED, CHARGEBACKED → CHARGEBACK.
    Delegates to shared process_successful_payment for balance crediting.

    Returns:
        Order | None
    """
    from shop.models import Order
    from shop.services.yoomoney import process_successful_payment

    order = (
        Order.objects.select_for_update()
        .filter(id=order_id, payment_provider="platega")
        .exclude(status="PAID")
        .first()
    )
    if not order:
        return None

    if status == Platega.STATUS_CONFIRMED:
        return process_successful_payment(order_id)

    if status == Platega.STATUS_CANCELED:
        order.status = "FAILED"
        order.save(update_fields=["status"])
        logger.info(f"[platega] Order #{order_id} canceled")
        return order

    if status == Platega.STATUS_CHARGEBACKED:
        order.status = "CHARGEBACK"
        order.save(update_fields=["status"])
        logger.info(f"[platega] Order #{order_id} chargebacked")
        return order

    return None
