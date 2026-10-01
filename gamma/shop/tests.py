from datetime import datetime, timedelta, timezone  # noqa: F401
from decimal import Decimal
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch
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

__all__ = ("PaymentTests", "TariffChangeLockTests", "ReferralTests")


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

    @patch("shop.views.RemnawaveClient")
    @patch("shop.views.verify_telegram_init_data")
    def test_extend_sub_api_reactivates_expired_users(
        self,
        mock_verify,
        mock_client_class,
    ):
        mock_verify.return_value = (True, {"id": 12345})
        self.profile.balance = Decimal("200.00")
        self.profile.tarif = self.tariff
        self.profile.whitelist_uuid = "whitelist-uuid"
        self.profile.save(update_fields=["balance", "tarif", "whitelist_uuid"])

        mock_client = mock_client_class.return_value
        mock_client.get_user_by_tgid = AsyncMock(
            return_value=[
                {
                    "uuid": "whitelist-uuid",
                    "username": "testuser_wl",
                    "status": "EXPIRED",
                    "expireAt": "2020-01-01T00:00:00.000Z",
                },
                {
                    "uuid": "main-uuid",
                    "username": "testuser",
                    "status": "EXPIRED",
                    "expireAt": "2020-01-01T00:00:00.000Z",
                },
            ],
        )
        mock_client.get_user = AsyncMock(
            return_value={
                "uuid": "whitelist-uuid",
                "expireAt": "2020-01-01T00:00:00.000Z",
            },
        )
        mock_client.update_user = AsyncMock()
        mock_client.close = AsyncMock()

        response = self.client.post(
            reverse("extend_sub_api"),
            {"init_data": "mock_data", "months": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        update_calls = mock_client.update_user.await_args_list
        self.assertEqual(len(update_calls), 2)
        self.assertTrue(
            all(call.kwargs["status"] == "ACTIVE" for call in update_calls),
        )

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

    @patch("shop.views.verify_telegram_init_data")
    @patch("shop.views.RemnawaveClient")
    def test_buy_slot_creates_order(
        self,
        mock_client_class,
        mock_verify,
    ):
        mock_verify.return_value = (
            True,
            {"id": 12345, "username": "testuser"},
        )
        mock_client = mock_client_class.return_value
        mock_client.get_user_by_tgid = AsyncMock(
            return_value={
                "uuid": "main-uuid",
                "hwidDeviceLimit": 1,
            },
        )
        mock_client.update_user = AsyncMock(
            return_value={"hwidDeviceLimit": 2},
        )
        mock_client.close = AsyncMock()

        response = self.client.post(
            reverse("buy_slot_api"),
            {"init_data": "mock_data"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["new_limit"], 2)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("0.00"))

        order = Order.objects.get(telegram_id=12345, order_type="SLOT")
        self.assertEqual(order.status, "PAID")
        self.assertEqual(order.amount, Decimal("100.00"))

    @patch("shop.views.verify_telegram_init_data")
    @patch("shop.views.RemnawaveClient")
    def test_buy_slot_failure_marks_order_failed(
        self,
        mock_client_class,
        mock_verify,
    ):
        mock_verify.return_value = (
            True,
            {"id": 12345, "username": "testuser"},
        )
        mock_client = mock_client_class.return_value
        mock_client.get_user_by_tgid = AsyncMock(
            side_effect=ValueError("RW down"),
        )
        mock_client.close = AsyncMock()

        response = self.client.post(
            reverse("buy_slot_api"),
            {"init_data": "mock_data"},
        )

        self.assertEqual(response.status_code, 500)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("100.00"))

        order = Order.objects.get(telegram_id=12345, order_type="SLOT")
        self.assertEqual(order.status, "FAILED")


class ReferralTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.referrer = Profile.objects.create(
            telegram_id=111,
            telegram_username="referrer",
            referral_code="REFCODE1",
        )
        self.invited = Profile.objects.create(
            telegram_id=222,
            telegram_username="invited",
            balance=Decimal("500.00"),
        )
        self.tariff = Tariff.objects.create(
            name="Ref Tariff",
            description="ref",
            price=Decimal("100.00"),
            duration_days=30,
            traffic_limit_bytes=0,
            device_limit=1,
        )
        self.tariff2 = Tariff.objects.create(
            name="Ref Tariff 2",
            description="ref2",
            price=Decimal("100.00"),
            duration_days=30,
            traffic_limit_bytes=0,
            device_limit=1,
        )
        settings.DEBUG = False

    def _post(self, name, tg_id, data):
        with patch(
            "shop.views.verify_telegram_init_data",
        ) as mock_verify:
            mock_verify.return_value = (True, {"id": tg_id, "username": "u"})
            payload = dict(data)
            payload["init_data"] = "mock_data"
            return self.client.post(reverse(name), payload)

    def _buy(self, tg_id, tariff):
        with (
            patch(
                "shop.views.RemnawaveClient",
            ) as mock_client_class,
            patch(
                "shop.views.verify_telegram_init_data",
            ) as mock_verify,
            patch(
                "shop.views.requests.post",
            ),
        ):
            mock_verify.return_value = (True, {"id": tg_id, "username": "u"})
            mock_client = mock_client_class.return_value
            mock_client.get_user_by_tgid = AsyncMock(
                return_value=[],
            )
            mock_client.create_user = AsyncMock(
                return_value={
                    "uuid": "new-uuid",
                    "expireAt": "2030-01-01T00:00:00.000Z",
                },
            )
            mock_client.close = AsyncMock()
            return self.client.post(
                reverse("buy_tariff_api"),
                {"tariff_id": tariff.id, "init_data": "mock_data"},
            )

    def test_bind_success(self):
        response = self._post(
            "bind_referral_api",
            222,
            {"ref_code": "refcode1"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["bound"])

        self.invited.refresh_from_db()
        self.assertEqual(self.invited.referred_by_id, self.referrer.pk)

    def test_bind_self_rejected(self):
        self.invited.referral_code = "OWNCODE1"
        self.invited.save(update_fields=["referral_code"])

        response = self._post(
            "bind_referral_api",
            222,
            {"ref_code": "OWNCODE1"},
        )

        data = response.json()
        self.assertFalse(data["bound"])
        self.assertEqual(data["reason"], "invalid")

    def test_bind_twice_rejected(self):
        self._post("bind_referral_api", 222, {"ref_code": "REFCODE1"})

        Profile.objects.create(
            telegram_id=333,
            referral_code="REFCODE2",
        )
        response = self._post(
            "bind_referral_api",
            222,
            {"ref_code": "REFCODE2"},
        )

        data = response.json()
        self.assertFalse(data["bound"])
        self.assertEqual(data["reason"], "already_bound")

        self.invited.refresh_from_db()
        self.assertEqual(self.invited.referred_by_id, self.referrer.pk)

    def test_bind_after_purchase_rejected(self):
        Order.objects.create(
            tariff=self.tariff,
            telegram_id=222,
            amount=Decimal("100.00"),
            order_type="PURCHASE",
            status="PAID",
        )

        response = self._post(
            "bind_referral_api",
            222,
            {"ref_code": "REFCODE1"},
        )

        data = response.json()
        self.assertFalse(data["bound"])
        self.assertEqual(data["reason"], "already_customer")

    def test_referral_info(self):
        response = self._post("referral_info_api", 111, {})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["code"], "REFCODE1")
        self.assertIn("start=ref_REFCODE1", data["link"])
        self.assertEqual(data["invited"], 0)
        self.assertEqual(data["earned"], 0)
        self.assertEqual(data["reward"], 100)

    def test_sync_data_includes_referral(self):
        with (
            patch(
                "shop.views.RemnawaveClient",
            ) as mock_client_class,
            patch(
                "shop.views.verify_telegram_init_data",
            ) as mock_verify,
        ):
            mock_verify.return_value = (
                True,
                {"id": 111, "username": "referrer"},
            )
            mock_client = mock_client_class.return_value
            mock_client.get_nodes = AsyncMock(return_value=[])
            mock_client.get_user_by_tgid = AsyncMock(return_value=[])
            mock_client.close = AsyncMock()
            response = self.client.post(
                reverse("sync_data_api"),
                {"init_data": "mock_data"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("referral", data)
        self.assertEqual(data["referral"]["code"], "REFCODE1")
        self.assertIn("start=ref_REFCODE1", data["referral"]["link"])
        self.assertEqual(data["referral"]["invited"], 0)
        self.assertEqual(data["referral"]["earned"], 0)

    def test_referrer_gets_telegram_notification(self):
        self._post("bind_referral_api", 222, {"ref_code": "REFCODE1"})

        with (
            patch(
                "shop.views.RemnawaveClient",
            ) as mock_client_class,
            patch(
                "shop.views.verify_telegram_init_data",
            ) as mock_verify,
            patch(
                "shop.views.requests.post",
            ) as mock_post,
        ):
            mock_verify.return_value = (True, {"id": 222, "username": "u"})
            mock_client = mock_client_class.return_value
            mock_client.get_user_by_tgid = AsyncMock(
                return_value=[],
            )
            mock_client.create_user = AsyncMock(
                return_value={
                    "uuid": "new-uuid",
                    "expireAt": "2030-01-01T00:00:00.000Z",
                },
            )
            mock_client.close = AsyncMock()
            response = self.client.post(
                reverse("buy_tariff_api"),
                {"tariff_id": self.tariff.id, "init_data": "mock_data"},
            )

        self.assertTrue(response.json()["success"])
        mock_post.assert_called_once()
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        self.assertIn("sendMessage", url)
        self.assertEqual(kwargs["json"]["chat_id"], 111)
        self.assertIn("100", kwargs["json"]["text"])
        self.assertIn("реферала", kwargs["json"]["text"])

    def test_no_notification_on_second_purchase(self):
        self._post("bind_referral_api", 222, {"ref_code": "REFCODE1"})
        self._buy(222, self.tariff)

        with (
            patch(
                "shop.views.RemnawaveClient",
            ) as mock_client_class,
            patch(
                "shop.views.verify_telegram_init_data",
            ) as mock_verify,
            patch(
                "shop.views.requests.post",
            ) as mock_post,
        ):
            mock_verify.return_value = (True, {"id": 222, "username": "u"})
            mock_client = mock_client_class.return_value
            mock_client.get_user_by_tgid = AsyncMock(
                return_value=[],
            )
            mock_client.create_user = AsyncMock(
                return_value={
                    "uuid": "new-uuid",
                    "expireAt": "2030-01-01T00:00:00.000Z",
                },
            )
            mock_client.close = AsyncMock()
            self.client.post(
                reverse("buy_tariff_api"),
                {"tariff_id": self.tariff2.id, "init_data": "mock_data"},
            )

        mock_post.assert_not_called()

    def test_reward_on_first_purchase(self):
        self._post("bind_referral_api", 222, {"ref_code": "REFCODE1"})

        response = self._buy(222, self.tariff)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        self.referrer.refresh_from_db()
        self.assertEqual(self.referrer.balance, Decimal("100.00"))
        self.assertEqual(self.referrer.referral_earned, Decimal("100.00"))

        reward_order = Order.objects.get(
            telegram_id=111,
            order_type="REFERRAL",
        )
        self.assertEqual(reward_order.status, "PAID")
        self.assertEqual(reward_order.amount, Decimal("100.00"))

        self.invited.refresh_from_db()
        self.assertTrue(self.invited.referral_reward_paid)

    def test_no_double_reward(self):
        self._post("bind_referral_api", 222, {"ref_code": "REFCODE1"})
        self._buy(222, self.tariff)
        self._buy(222, self.tariff2)

        self.referrer.refresh_from_db()
        self.assertEqual(self.referrer.balance, Decimal("100.00"))
        self.assertEqual(
            Order.objects.filter(
                telegram_id=111,
                order_type="REFERRAL",
            ).count(),
            1,
        )

    def test_no_reward_without_referrer(self):
        self._buy(222, self.tariff)

        self.assertFalse(
            Order.objects.filter(order_type="REFERRAL").exists(),
        )


class TariffChangeLockTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.locked_tariff = Tariff.objects.create(
            name="Locked Tariff",
            description="locked",
            price=Decimal("100.00"),
            duration_days=30,
            traffic_limit_bytes=0,
            device_limit=1,
            change_locked=True,
        )
        self.plain_tariff = Tariff.objects.create(
            name="Plain Tariff",
            description="plain",
            price=Decimal("100.00"),
            duration_days=30,
            traffic_limit_bytes=0,
            device_limit=1,
        )
        self.other_tariff = Tariff.objects.create(
            name="Other Tariff",
            description="other",
            price=Decimal("100.00"),
            duration_days=30,
            traffic_limit_bytes=0,
            device_limit=1,
        )
        self.profile = Profile.objects.create(
            telegram_id=54321,
            balance=Decimal("500.00"),
        )
        settings.DEBUG = False

    def _buy(self, tariff):
        with patch(
            "shop.views.verify_telegram_init_data",
        ) as mock_verify:
            mock_verify.return_value = (
                True,
                {"id": 54321, "username": "lockuser"},
            )
            return self.client.post(
                reverse("buy_tariff_api"),
                {"tariff_id": tariff.id, "init_data": "mock_data"},
            )

    def _buy_with_mocked_rw(self, tariff):
        with patch(
            "shop.views.RemnawaveClient",
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.get_user_by_tgid = AsyncMock(
                return_value=[],
            )
            mock_client.create_user = AsyncMock(
                return_value={
                    "uuid": "new-uuid",
                    "expireAt": "2030-01-01T00:00:00.000Z",
                },
            )
            mock_client.close = AsyncMock()
            return self._buy(tariff)

    def test_change_from_locked_tariff_blocked(self):
        self.profile.tarif = self.locked_tariff
        self.profile.save(update_fields=["tarif"])

        response = self._buy(self.plain_tariff)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"],
            "tariff_change_locked",
        )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.tarif.id, self.locked_tariff.id)
        self.assertEqual(self.profile.balance, Decimal("500.00"))
        self.assertFalse(
            Order.objects.filter(
                telegram_id=54321,
                tariff=self.plain_tariff,
            ).exists(),
        )

    def test_rebuy_same_locked_tariff_allowed(self):
        self.profile.tarif = self.locked_tariff
        self.profile.save(update_fields=["tarif"])

        response = self._buy_with_mocked_rw(self.locked_tariff)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["tariff_change_locked"])

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.tarif.id, self.locked_tariff.id)
        self.assertEqual(self.profile.balance, Decimal("400.00"))

    def test_buy_locked_tariff_without_current_allowed(self):
        response = self._buy_with_mocked_rw(self.locked_tariff)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.tarif.id, self.locked_tariff.id)

    def test_change_from_unlocked_tariff_allowed(self):
        self.profile.tarif = self.plain_tariff
        self.profile.save(update_fields=["tarif"])

        response = self._buy_with_mocked_rw(self.other_tariff)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.tarif.id, self.other_tariff.id)
