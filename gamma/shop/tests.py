from datetime import datetime, timedelta, timezone  # noqa: F401
from decimal import Decimal
import hashlib
import hmac
import json
import time
from unittest.mock import patch
from urllib.parse import urlencode

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from shop.models import Order, Tariff
from shop.services.yoomoney import (
    cancel_expired_orders,
    process_successful_payment,
    verify_payment_api,
)
from shop.utils import verify_telegram_init_data
from user.models import Profile

__all__ = ("PaymentTests",)


class TelegramInitDataTests(TestCase):
    def _build_init_data(self, auth_date):
        data = {
            "auth_date": str(auth_date),
            "query_id": "test-query",
            "user": json.dumps({"id": 12345}),
        }
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(data.items())
        )
        secret_key = hmac.new(
            b"WebAppData",
            settings.BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()
        data["hash"] = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        return urlencode(data)

    def test_verify_telegram_init_data_rejects_expired_data(self):
        init_data = self._build_init_data(int(time.time()) - 301)

        self.assertEqual(verify_telegram_init_data(init_data), (False, None))

    def test_verify_telegram_init_data_accepts_fresh_data(self):
        init_data = self._build_init_data(int(time.time()))

        self.assertEqual(
            verify_telegram_init_data(init_data),
            (True, {"id": 12345}),
        )


class PaymentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.profile = Profile.objects.create(
            telegram_id=12345,
            balance=Decimal("100.00"),
        )
        self.tariff = Tariff.objects.create(
            name="Test Tariff",
            price=Decimal("150.00"),
            duration_days=30,
            traffic_limit_bytes=1000,
            device_limit=1,
        )
        settings.DEBUG = False

    @patch("shop.views.verify_telegram_init_data")
    def test_topup_api_creates_pending_order(self, mock_verify):
        mock_verify.return_value = (
            True,
            {"id": 12345, "username": "testuser"},
        )
        settings.YOOMONEY_RECEIVER = "410019014512803"

        response = self.client.post(
            reverse("topup_api"),
            {"init_data": "mock_data", "amount": "500"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("payment_url", data)
        self.assertIn("order_id", data)
        self.assertTrue(data["payment_url"].startswith("https://yoomoney.ru/"))

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("100.00"))

        order = Order.objects.get(telegram_id=12345, amount=Decimal("500.00"))
        self.assertEqual(order.id, data["order_id"])
        self.assertEqual(order.status, "PENDING")

    @patch("shop.views.verify_telegram_init_data")
    def test_topup_api_debug_returns_payment_url(self, mock_verify):
        mock_verify.return_value = (
            True,
            {"id": 12345, "username": "testuser"},
        )
        settings.DEBUG = True
        settings.YOOMONEY_RECEIVER = "410019014512803"

        response = self.client.post(
            reverse("topup_api"),
            {"init_data": "mock_data", "amount": "200"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("payment_url", data)
        self.assertIn("order_id", data)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("100.00"))

        order = Order.objects.get(telegram_id=12345, amount=Decimal("200.00"))
        self.assertEqual(order.status, "PENDING")

        settings.DEBUG = False

    @patch("shop.views.verify_telegram_init_data")
    def test_buy_tariff_insufficient_funds(self, mock_verify):
        mock_verify.return_value = (
            True,
            {"id": 12345, "username": "testuser"},
        )

        response = self.client.post(
            reverse("buy_tariff_api"),
            {"tariff_id": self.tariff.id, "init_data": "mock_data"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "insufficient_funds")

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("100.00"))

    def test_verify_payment_api(self):
        settings.YOOMONEY_TOKEN = ""
        result = verify_payment_api(1, Decimal("100.00"))
        self.assertFalse(result)

    def test_process_successful_payment_valid(self):
        order = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("500.00"),
            order_type="TOPUP",
            status="PENDING",
        )
        settings.ORDER_TIMEOUT_MINUTES = 10

        result = process_successful_payment(order.id)
        self.assertIsNotNone(result)

        order.refresh_from_db()
        self.assertEqual(order.status, "PAID")

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("600.00"))

    def test_process_successful_payment_expired_still_credits(self):
        old_date = datetime.now(timezone.utc) - timedelta(minutes=15)
        order = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("500.00"),
            order_type="TOPUP",
            status="PENDING",
        )
        Order.objects.filter(id=order.id).update(created_at=old_date)
        settings.ORDER_TIMEOUT_MINUTES = 10

        result = process_successful_payment(order.id)
        self.assertIsNotNone(result)

        order.refresh_from_db()
        self.assertEqual(order.status, "PAID")

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("600.00"))

    def test_cancel_expired_orders(self):
        old_date = datetime.now(timezone.utc) - timedelta(minutes=15)
        order1 = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("100.00"),
            order_type="TOPUP",
            status="PENDING",
        )
        Order.objects.filter(id=order1.id).update(created_at=old_date)

        order2 = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("200.00"),
            order_type="TOPUP",
            status="PENDING",
        )

        settings.ORDER_TIMEOUT_MINUTES = 10
        count = cancel_expired_orders()
        self.assertEqual(count, 1)

        order1.refresh_from_db()
        self.assertEqual(order1.status, "FAILED")

        order2.refresh_from_db()
        self.assertEqual(order2.status, "PENDING")

    def test_check_payment_api_pending(self):
        order = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("500.00"),
            order_type="TOPUP",
            status="PENDING",
        )

        session = self.client.session
        session["tg_user"] = {"id": 12345}
        session.save()

        response = self.client.get(
            reverse("check_payment_api", args=[order.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")

    def test_check_payment_api_paid(self):
        order = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("500.00"),
            order_type="TOPUP",
            status="PAID",
        )

        session = self.client.session
        session["tg_user"] = {"id": 12345}
        session.save()

        response = self.client.get(
            reverse("check_payment_api", args=[order.id]),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "paid")

    def test_check_payment_api_forbidden(self):
        order = Order.objects.create(
            telegram_id=99999,
            amount=Decimal("500.00"),
            order_type="TOPUP",
            status="PENDING",
        )

        session = self.client.session
        session["tg_user"] = {"id": 12345}
        session.save()

        response = self.client.get(
            reverse("check_payment_api", args=[order.id]),
        )

        self.assertEqual(response.status_code, 403)

    def test_check_payment_api_debug_simulates_after_15s(self):
        settings.DEBUG = True
        order = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("500.00"),
            order_type="TOPUP",
            status="PENDING",
        )
        Order.objects.filter(id=order.id).update(
            created_at=datetime.now(timezone.utc) - timedelta(seconds=20),
        )

        session = self.client.session
        session["tg_user"] = {"id": 12345}
        session.save()

        response = self.client.get(
            reverse("check_payment_api", args=[order.id]),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "paid")

        order.refresh_from_db()
        self.assertEqual(order.status, "PAID")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("600.00"))

        settings.DEBUG = False

    def test_check_payment_api_debug_still_pending_before_15s(self):
        settings.DEBUG = True
        order = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("500.00"),
            order_type="TOPUP",
            status="PENDING",
        )

        session = self.client.session
        session["tg_user"] = {"id": 12345}
        session.save()

        response = self.client.get(
            reverse("check_payment_api", args=[order.id]),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "pending")
        order.refresh_from_db()
        self.assertEqual(order.status, "PENDING")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("100.00"))

        settings.DEBUG = False

    def test_check_payment_api_not_found(self):
        response = self.client.get(
            reverse("check_payment_api", args=[999]),
        )
        self.assertEqual(response.status_code, 404)

    def test_sync_data_api_requires_post(self):
        response = self.client.get(reverse("sync_data_api"))

        self.assertEqual(response.status_code, 405)

    def test_get_subscription_link_api_requires_post(self):
        response = self.client.get(reverse("get_subscription_link_api"))

        self.assertEqual(response.status_code, 405)

    @patch("shop.views.verify_telegram_init_data")
    @patch("shop.views.create_platega_payment")
    def test_topup_api_platega_sbp(self, mock_create, mock_verify):
        mock_verify.return_value = (
            True,
            {"id": 12345, "username": "testuser"},
        )
        mock_create.return_value = (
            "https://platega.io/pay/xyz",
            "platega-tx-123",
        )
        settings.PLATEGA_MERCHANT_ID = "test-merchant"
        settings.PLATEGA_SECRET = "test-secret"

        response = self.client.post(
            reverse("topup_api"),
            {
                "init_data": "mock_data",
                "amount": "300",
                "payment_provider": "sbp",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["payment_url"], "https://platega.io/pay/xyz")
        self.assertEqual(
            Order.objects.filter(
                telegram_id=12345,
                payment_provider="platega",
                platega_transaction_id="platega-tx-123",
            ).count(),
            1,
        )

    @patch("shop.views.verify_telegram_init_data")
    @patch("shop.views.verify_platega_payment")
    def test_check_payment_api_platega_confirmed(
        self,
        mock_verify_platega,
        mock_verify_tg,
    ):
        mock_verify_tg.return_value = (True, {"id": 12345})
        mock_verify_platega.return_value = "CONFIRMED"
        settings.DEBUG = False

        order = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("300.00"),
            order_type="TOPUP",
            status="PENDING",
            payment_provider="platega",
            platega_transaction_id="platega-tx-123",
        )

        session = self.client.session
        session["tg_user"] = {"id": 12345}
        session.save()

        response = self.client.get(
            reverse("check_payment_api", args=[order.id]),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "paid")
        self.assertEqual(
            data["new_balance"],
            400.0,
        )  # 100.0 initial in setUp + 300.0

        order.refresh_from_db()
        self.assertEqual(order.status, "PAID")

    @patch("shop.views.PlategaCallback.validate_django")
    @patch("shop.views.PlategaCallback.get_order_id")
    @patch("shop.views.PlategaCallback.get_status")
    def test_platega_callback_webhook(
        self,
        mock_status,
        mock_order_id,
        mock_validate,
    ):
        settings.PLATEGA_MERCHANT_ID = "test-merchant"
        settings.PLATEGA_SECRET = "test-secret"

        order = Order.objects.create(
            telegram_id=12345,
            amount=Decimal("150.00"),
            order_type="TOPUP",
            status="PENDING",
            payment_provider="platega",
            platega_transaction_id="platega-tx-999",
        )

        mock_validate.return_value = True
        mock_order_id.return_value = str(order.id)
        mock_status.return_value = "CONFIRMED"

        response = self.client.post(
            reverse("platega_callback"),
            data=json.dumps({"dummy": "data"}),
            content_type="application/json",
            HTTP_X_MERCHANTID="test-merchant",
            HTTP_X_SECRET="test-secret",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

        order.refresh_from_db()
        self.assertEqual(order.status, "PAID")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("250.00"))
