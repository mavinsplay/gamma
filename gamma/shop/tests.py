from datetime import datetime, timedelta, timezone  # noqa: F401
from decimal import Decimal
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode

from django.conf import settings
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from shop.models import Order, Tariff
from shop.services.yoomoney import (
    cancel_expired_orders,
    process_successful_payment,
    verify_payment_api,
)
from shop.utils import verify_telegram_init_data
from user.models import Profile

__all__ = (
    "PaymentTests",
    "TariffChangeLockTests",
    "ReferralTests",
    "BillingTests",
    "PayoutWorkerTests",
)


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


class BillingTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        self.client = Client()
        # Кэш общий между прогонами — чистим для детерминированности.
        cache.clear()
        # YooMoney-блок мокаем: иначе тесты полезут в сеть по живым
        # кредам из .env.
        yo_patch = patch("shop.services.billing.get_yoomoney_block")
        self.mock_yo = yo_patch.start()
        self.mock_yo.return_value = {
            "balance": None,
            "account_masked": None,
            "error": True,
            "daily": {},
            "total": 0.0,
        }
        self.addCleanup(yo_patch.stop)
        self._old_admin = settings.ADMIN_TELEGRAM_ID
        self._old_payout_secret = settings.PLATEGA_PAYOUT_SECRET
        settings.ADMIN_TELEGRAM_ID = 999
        settings.DEBUG = False
        # UI-вывод и автопорог в тестах всегда выключены (.env живой
        # среды может их включать) — нужное включает _enable_ui_payout.
        self._old_ui = {
            "login": settings.PLATEGA_UI_LOGIN,
            "password": settings.PLATEGA_UI_PASSWORD,
            "login_url": settings.PLATEGA_UI_LOGIN_URL,
            "payout_url": settings.PLATEGA_UI_PAYOUT_URL,
            "last4": settings.PLATEGA_PAYOUT_CARD_LAST4,
            "auto": settings.PLATEGA_AUTOPAYOUT_ENABLED,
            "threshold": settings.PLATEGA_AUTOPAYOUT_THRESHOLD_RUB,
        }
        settings.PLATEGA_UI_LOGIN = ""
        settings.PLATEGA_UI_PASSWORD = ""
        settings.PLATEGA_UI_LOGIN_URL = ""
        settings.PLATEGA_UI_PAYOUT_URL = ""
        settings.PLATEGA_PAYOUT_CARD_LAST4 = ""
        settings.PLATEGA_AUTOPAYOUT_ENABLED = False
        self.addCleanup(self._restore_settings)

    def _restore_settings(self):
        settings.ADMIN_TELEGRAM_ID = self._old_admin
        settings.PLATEGA_PAYOUT_SECRET = self._old_payout_secret
        settings.PLATEGA_UI_LOGIN = self._old_ui["login"]
        settings.PLATEGA_UI_PASSWORD = self._old_ui["password"]
        settings.PLATEGA_UI_LOGIN_URL = self._old_ui["login_url"]
        settings.PLATEGA_UI_PAYOUT_URL = self._old_ui["payout_url"]
        settings.PLATEGA_PAYOUT_CARD_LAST4 = self._old_ui["last4"]
        settings.PLATEGA_AUTOPAYOUT_ENABLED = self._old_ui["auto"]
        settings.PLATEGA_AUTOPAYOUT_THRESHOLD_RUB = self._old_ui["threshold"]

    def _post_admin(self, name, data):
        with patch(
            "shop.views_billing._get_authorized_telegram_id",
        ) as mock_auth:
            mock_auth.return_value = 999
            return self.client.post(reverse(name), data)

    def _make_topup(self, amount, provider, method, status="PAID"):
        return Order.objects.create(
            telegram_id=111,
            amount=Decimal(str(amount)),
            order_type="TOPUP",
            status=status,
            payment_provider=provider,
            payment_method=method,
        )

    def test_stats_split_and_net(self):
        from shop.services.billing import get_billing_stats

        self._make_topup("1000.00", "yoomoney", "card")
        self._make_topup("500.00", "platega", "sbp")
        self._make_topup("200.00", "platega", "crypto")
        self._make_topup("100.00", "platega", "")
        # Внутренние движения — не доход
        Order.objects.create(
            telegram_id=111,
            amount=Decimal("999.00"),
            order_type="PURCHASE",
            status="PAID",
            payment_provider="yoomoney",
        )
        Order.objects.create(
            telegram_id=111,
            amount=Decimal("100.00"),
            order_type="REFERRAL",
            status="PAID",
            payment_provider="yoomoney",
        )
        self._make_topup("50.00", "yoomoney", "card", status="PENDING")

        stats = get_billing_stats(days=365)
        channels = stats["period"]["channels"]
        self.assertEqual(channels["card"]["gross"], 1000.00)
        self.assertEqual(channels["card"]["net"], 970.00)
        self.assertEqual(channels["sbp"]["gross"], 500.00)
        self.assertEqual(channels["sbp"]["net"], 480.00)
        self.assertEqual(channels["crypto"]["gross"], 200.00)
        self.assertEqual(channels["crypto"]["net"], 192.00)
        self.assertEqual(channels["platega_other"]["gross"], 100.00)
        self.assertEqual(channels["platega_other"]["net"], 96.00)
        self.assertEqual(stats["period"]["gross"], 1800.00)
        self.assertEqual(stats["period"]["net"], 1738.00)
        self.assertEqual(stats["period"]["count"], 4)

    def test_timeline_has_today(self):
        from django.utils import timezone

        from shop.services.billing import get_billing_stats

        self._make_topup("300.00", "yoomoney", "card")
        stats = get_billing_stats(days=7)
        today = timezone.now().date().isoformat()
        days = {p["date"]: p for p in stats["timeline"]}
        self.assertIn(today, days)
        self.assertEqual(days[today]["card"], 291.00)
        self.assertEqual(days[today]["total"], 291.00)
        self.assertEqual(days[today]["gross"], 300.00)
        self.assertEqual(days[today]["refund"], 0.00)

    def test_timeline_counts_refunds(self):
        from django.utils import timezone

        from shop.services.billing import get_billing_stats

        self._make_topup("300.00", "yoomoney", "card")
        Order.objects.create(
            telegram_id=111,
            amount=Decimal("100.00"),
            order_type="TOPUP",
            status="REFUNDED",
            payment_provider="yoomoney",
            payment_method="card",
        )
        stats = get_billing_stats(days=7)
        today = timezone.now().date().isoformat()
        days = {p["date"]: p for p in stats["timeline"]}
        self.assertEqual(days[today]["refund"], 100.00)
        self.assertEqual(stats["period"]["refunds"], 100.00)
        # Возвраты не раздувают доход
        self.assertEqual(stats["period"]["gross"], 300.00)

    def test_top_payers(self):
        from user.models import Profile

        from shop.services.billing import get_top_payers

        Profile.objects.create(
            telegram_id=111,
            telegram_username="whale",
        )
        Profile.objects.create(
            telegram_id=222,
            telegram_username="fish",
        )
        self._make_topup("1000.00", "yoomoney", "card")
        Order.objects.create(
            telegram_id=222,
            amount=Decimal("200.00"),
            order_type="TOPUP",
            status="PAID",
            payment_provider="platega",
            payment_method="sbp",
        )
        payers = get_top_payers(limit=10)
        self.assertEqual(len(payers), 2)
        self.assertEqual(payers[0]["telegram_id"], 111)
        self.assertEqual(payers[0]["username"], "whale")
        self.assertEqual(payers[0]["total"], 1000.00)
        self.assertEqual(payers[0]["count"], 1)
        self.assertEqual(payers[1]["total"], 200.00)

    def test_billing_api_forbidden_for_non_admin(self):
        with patch(
            "shop.views_billing._get_authorized_telegram_id",
        ) as mock_auth:
            mock_auth.return_value = 123
            for name in (
                "billing_api",
                "billing_server_api",
                "billing_payout_api",
            ):
                response = self.client.post(reverse(name), {})
                self.assertEqual(response.status_code, 403)

    def test_billing_api_ok_admin(self):
        with (
            patch(
                "shop.views_billing.get_platega_balances",
            ) as mock_balances,
            patch(
                "shop.views_billing.get_usd_rub_rate",
                return_value=(80.0, "setting"),
            ),
        ):
            mock_balances.return_value = (
                [{"amount": 15000.5, "currency": "RUB"}],
                None,
            )
            response = self._post_admin("billing_api", {"days": "30"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("stats", data)
        self.assertIn("servers", data)
        self.assertIn("month_profit", data)
        self.assertFalse(data["payout_configured"])
        self.assertEqual(data["payout_cards"], [])
        self.assertEqual(
            data["balances"],
            [{"amount": 15000.5, "currency": "RUB"}],
        )

    def test_server_crud(self):
        response = self._post_admin(
            "billing_server_api",
            {
                "action": "create",
                "name": "VPS-1",
                "monthly_cost": "500",
                "pay_day": "15",
            },
        )
        self.assertEqual(response.status_code, 200)
        servers = response.json()["servers"]["servers"]
        self.assertEqual(len(servers), 1)
        server_id = servers[0]["id"]
        self.assertFalse(servers[0]["paid_this_month"])

        response = self._post_admin(
            "billing_server_api",
            {"action": "mark_paid", "id": server_id},
        )
        paid = response.json()["servers"]["servers"][0]
        self.assertTrue(paid["paid_this_month"])
        self.assertFalse(paid["overdue"])

        response = self._post_admin(
            "billing_server_api",
            {"action": "delete", "id": server_id},
        )
        self.assertEqual(
            response.json()["servers"]["servers"],
            [],
        )

    def test_server_invalid_day(self):
        response = self._post_admin(
            "billing_server_api",
            {
                "action": "create",
                "name": "VPS",
                "monthly_cost": "500",
                "pay_day": "32",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_server_auto_paid_on_due_day(self):
        from django.utils import timezone

        from shop.models import ServerExpense
        from shop.services.billing import get_servers_data

        today = timezone.now().date()
        ServerExpense.objects.create(
            name="auto",
            monthly_cost=Decimal("500"),
            pay_day=today.day,
        )
        item = get_servers_data()["servers"][0]
        # Кнопку не нажимали — прожалось само
        self.assertTrue(item["auto_paid"])
        self.assertFalse(item["paid_this_month"])
        self.assertFalse(item["overdue"])
        self.assertIsNone(item["last_paid"])

    def test_server_not_auto_before_due_day(self):
        from django.utils import timezone

        from shop.models import ServerExpense
        from shop.services.billing import get_servers_data

        today = timezone.now().date()
        if today.day >= 31:
            self.skipTest("31-е число: будущего дня оплаты в месяце нет")

        ServerExpense.objects.create(
            name="future",
            monthly_cost=Decimal("500"),
            pay_day=today.day + 1,
        )
        item = get_servers_data()["servers"][0]
        self.assertFalse(item["auto_paid"])
        self.assertFalse(item["paid_this_month"])

    def test_timeline_server_expenses_and_upcoming(self):
        from django.utils import timezone

        from shop.models import ServerExpense
        from shop.services.billing import get_billing_stats

        today = timezone.now().date()
        ServerExpense.objects.create(
            name="srv",
            monthly_cost=Decimal("500"),
            pay_day=today.day,
        )
        stats = get_billing_stats(days=7)
        days_map = {p["date"]: p for p in stats["timeline"]}
        # Списание легло на день оплаты — вниз, как расход
        self.assertEqual(days_map[today.isoformat()]["servers"], -500.0)
        # У всех точек графика есть ключ servers
        self.assertTrue(all("servers" in p for p in stats["timeline"]))

    def test_timeline_manual_payment_replaces_auto(self):
        from django.utils import timezone

        from shop.models import ServerExpense
        from shop.services.billing import get_billing_stats

        today = timezone.now().date()
        if today.day < 4:
            self.skipTest("начало месяца: нет прошлого дня оплаты")

        pay_day = today.day - 2
        ServerExpense.objects.create(
            name="manual",
            monthly_cost=Decimal("500"),
            pay_day=pay_day,
            last_paid=today,
        )
        first = today.replace(day=1)
        stats = get_billing_stats(date_from=first, date_to=today)
        days_map = {p["date"]: p for p in stats["timeline"]}
        # Трата в день нажатия кнопки...
        self.assertEqual(days_map[today.isoformat()]["servers"], -500.0)
        # ...авто-точка в день оплаты в этом месяце гаснет.
        auto_day = today.replace(day=pay_day).isoformat()
        self.assertEqual(days_map[auto_day]["servers"], 0.0)

    def test_timeline_upcoming_expense_within_month(self):
        from django.utils import timezone

        from shop.models import ServerExpense
        from shop.services.billing import get_billing_stats

        today = timezone.now().date()
        if today.day > 28:
            self.skipTest("конец месяца: нет дня оплаты +2 в этом месяце")

        ServerExpense.objects.create(
            name="up",
            monthly_cost=Decimal("300"),
            pay_day=today.day + 2,
        )
        stats = get_billing_stats(days=7)
        days_map = {p["date"]: p for p in stats["timeline"]}
        iso = (today + timedelta(days=2)).isoformat()
        self.assertIn(iso, days_map)
        self.assertEqual(days_map[iso]["servers"], -300.0)
        # График продлён в будущее ровно до предстоящего списания
        self.assertEqual(stats["timeline"][-1]["date"], iso)

    def test_period_profit_with_expenses(self):
        from django.utils import timezone

        from shop.models import LedgerEntry, ServerExpense
        from shop.services.billing import get_billing_stats

        today = timezone.now().date()
        self._make_topup("1000.00", "yoomoney", "card")
        ServerExpense.objects.create(
            name="srv",
            monthly_cost=Decimal("500"),
            pay_day=today.day,
        )
        LedgerEntry.objects.create(
            name="Бонус",
            amount=Decimal("232.00"),
            entry_date=today,
        )
        stats = get_billing_stats(days=7)
        # 970 чистыми − 500 сервер + 232 внеплановые
        self.assertEqual(stats["period"]["net"], 970.00)
        self.assertEqual(stats["period"]["profit"], 702.00)

    def test_timeline_includes_ledger(self):
        from django.utils import timezone

        from shop.models import LedgerEntry
        from shop.services.billing import get_billing_stats

        today = timezone.now().date()
        LedgerEntry.objects.create(
            name="Бонус",
            amount=Decimal("232.00"),
            entry_date=today,
        )
        stats = get_billing_stats(days=7)
        days_map = {p["date"]: p for p in stats["timeline"]}
        self.assertEqual(days_map[today.isoformat()]["ledger"], 232.00)
        self.assertEqual(stats["period"]["ledger"], 232.00)
        self.assertTrue(all("ledger" in p for p in stats["timeline"]))

    def test_ledger_prune_via_api(self):
        from django.utils import timezone

        from shop.models import LedgerEntry

        today = timezone.now().date()
        old = LedgerEntry.objects.create(
            name="Старое",
            amount=Decimal("100.00"),
            entry_date=today - timedelta(days=40),
        )
        fresh = LedgerEntry.objects.create(
            name="Свежее",
            amount=Decimal("50.00"),
            entry_date=today,
        )
        with (
            patch(
                "shop.views_billing.get_platega_balances",
            ) as mock_balances,
            patch(
                "shop.views_billing.get_usd_rub_rate",
                return_value=(80.0, "setting"),
            ),
        ):
            mock_balances.return_value = ([], None)
            response = self._post_admin("billing_api", {"days": "7"})

        self.assertEqual(response.status_code, 200)
        # Старше 31 дня — удалено, свежее — на месте
        self.assertFalse(LedgerEntry.objects.filter(id=old.id).exists())
        self.assertTrue(LedgerEntry.objects.filter(id=fresh.id).exists())
        names = [e["name"] for e in response.json()["ledger"]["entries"]]
        self.assertIn("Свежее", names)
        self.assertNotIn("Старое", names)

    def test_stats_custom_range(self):
        from django.utils import timezone

        from shop.services.billing import get_billing_stats

        self._make_topup("1000.00", "yoomoney", "card")
        old = self._make_topup("700.00", "yoomoney", "card")
        old.created_at = timezone.now() - timedelta(days=60)
        old.save()

        today = timezone.now().date()
        date_from = today - timedelta(days=3)
        stats = get_billing_stats(date_from=date_from, date_to=today)
        self.assertEqual(stats["days"], 0)
        self.assertEqual(stats["date_from"], date_from.isoformat())
        self.assertEqual(stats["date_to"], today.isoformat())
        # Старый заказ вне диапазона не попал в период
        self.assertEqual(stats["period"]["gross"], 1000.00)
        self.assertEqual(stats["period"]["count"], 1)
        self.assertEqual(stats["timeline"][0]["date"], date_from.isoformat())
        self.assertEqual(
            stats["timeline"][-1]["date"],
            today.isoformat(),
        )

    def test_billing_api_custom_range(self):
        from django.utils import timezone

        today = timezone.now().date()
        date_from = (today - timedelta(days=5)).isoformat()
        with patch(
            "shop.views_billing.get_platega_balances",
        ) as mock_balances:
            mock_balances.return_value = ([], None)
            response = self._post_admin(
                "billing_api",
                {"date_from": date_from, "date_to": today.isoformat()},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["stats"]["days"], 0)
        self.assertEqual(data["stats"]["date_from"], date_from)
        self.assertEqual(data["stats"]["date_to"], today.isoformat())

    def test_billing_api_invalid_range_falls_back_to_days(self):
        with patch(
            "shop.views_billing.get_platega_balances",
        ) as mock_balances:
            mock_balances.return_value = ([], None)
            response = self._post_admin(
                "billing_api",
                {"date_from": "2026-12-10", "date_to": "2026-12-01"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        # Кривой диапазон проигнорирован — обычный режим по days
        self.assertEqual(data["stats"]["days"], 30)

    def test_autopayout_save_and_read(self):
        from shop.services.billing import (
            get_autopayout_config,
            save_autopayout_config,
        )

        config, error = save_autopayout_config(
            {
                "enabled": "1",
                "threshold": "7000",
                "check_min": "10",
                "cooldown_min": "30",
            },
        )
        self.assertIsNone(error)
        self.assertTrue(config["enabled"])
        self.assertEqual(config["threshold"], 7000)
        self.assertEqual(config["check_min"], 10)
        self.assertEqual(config["cooldown_min"], 30)
        reread = get_autopayout_config()
        self.assertEqual(reread["threshold"], 7000)

        _config, error = save_autopayout_config(
            {
                "enabled": "1",
                "threshold": "100",
                "check_min": "10",
                "cooldown_min": "30",
            },
        )
        self.assertIsNotNone(error)

        _config, error = save_autopayout_config(
            {
                "enabled": "0",
                "threshold": "7000",
                "check_min": "0",
                "cooldown_min": "30",
            },
        )
        self.assertIsNotNone(error)

    def test_billing_autopayout_api(self):
        response = self._post_admin(
            "billing_autopayout_api",
            {
                "enabled": "1",
                "threshold": "12000",
                "check_min": "20",
                "cooldown_min": "45",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["autopayout"]["enabled"])
        self.assertEqual(data["autopayout"]["threshold"], 12000)
        self.assertEqual(data["autopayout"]["check_min"], 20)

        response = self._post_admin(
            "billing_autopayout_api",
            {
                "enabled": "1",
                "threshold": "5",
                "check_min": "20",
                "cooldown_min": "45",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_autopayout_config_db_over_env(self):
        from shop.models import BillingSetting
        from shop.services import payout_worker
        from shop.services.billing import get_autopayout_config

        self._enable_ui_payout()
        # В env выключено — включаем через БД панели
        BillingSetting.objects.create(key="autopayout_enabled", value="1")
        BillingSetting.objects.create(key="autopayout_threshold", value="5000")
        config = get_autopayout_config()
        self.assertTrue(config["enabled"])
        self.assertEqual(config["threshold"], 5000)
        with (
            patch.object(
                payout_worker,
                "get_withdrawable_rub",
                return_value=(6000.0, None),
            ),
            patch.object(
                payout_worker,
                "get_usd_rub_rate",
                return_value=(80.0, "setting"),
            ),
        ):
            job = payout_worker.schedule_auto_job()

        self.assertIsNotNone(job)
        self.assertEqual(float(job.amount), 5960.0)

    def test_payout_not_configured(self):
        response = self._post_admin(
            "billing_payout_api",
            {"amount": "1500", "card_number": "2200000000000000"},
        )
        self.assertEqual(response.status_code, 400)

    def test_payout_card_number_success(self):
        settings.PLATEGA_PAYOUT_SECRET = "payout-secret"
        with patch(
            "shop.views_billing.create_card_payout",
        ) as mock_payout:
            mock_payout.return_value = (
                {
                    "status": "CREATED",
                    "cardMasked": "**** 0000",
                    "amountUsdtDebited": 16.5,
                    "withdrawalRecordId": "w-1",
                },
                None,
            )
            with patch(
                "shop.views_billing._get_authorized_telegram_id",
            ) as mock_auth:
                mock_auth.return_value = 999
                response = self.client.post(
                    reverse("billing_payout_api"),
                    {
                        "amount": "1500",
                        "card_number": "2200 0000 0000 0000",
                    },
                )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["withdrawal_id"], "w-1")
        payout = Order.objects.get(order_type="PAYOUT")
        self.assertEqual(payout.amount, Decimal("1500.00"))
        self.assertEqual(payout.telegram_id, 999)
        self.assertEqual(payout.platega_transaction_id, "w-1")

    def test_payout_double_submit_rejected(self):
        settings.PLATEGA_PAYOUT_SECRET = "payout-secret"
        with patch(
            "shop.views_billing.create_card_payout",
        ) as mock_payout:
            mock_payout.return_value = (
                {
                    "status": "CREATED",
                    "cardMasked": "**** 0000",
                    "amountUsdtDebited": 16.5,
                    "withdrawalRecordId": "w-1",
                },
                None,
            )
            first = self._post_admin(
                "billing_payout_api",
                {"amount": "1500", "card_number": "2200000000000000"},
            )
            self.assertEqual(first.status_code, 200)
            second = self._post_admin(
                "billing_payout_api",
                {"amount": "1500", "card_number": "2200000000000000"},
            )

        self.assertEqual(second.status_code, 429)
        self.assertEqual(
            Order.objects.filter(order_type="PAYOUT").count(),
            1,
        )

    def test_payout_rejects_bounds_and_both_dests(self):
        settings.PLATEGA_PAYOUT_SECRET = "payout-secret"
        response = self._post_admin(
            "billing_payout_api",
            {"amount": "999", "card_number": "2200000000000000"},
        )
        self.assertEqual(response.status_code, 400)

        response = self._post_admin(
            "billing_payout_api",
            {"amount": "1500", "card_id": "x", "card_number": "2200"},
        )
        self.assertEqual(response.status_code, 400)

    def test_payout_unknown_card_id_rejected(self):
        settings.PLATEGA_PAYOUT_SECRET = "payout-secret"
        with patch(
            "shop.views_billing.get_payout_cards",
        ) as mock_cards:
            mock_cards.return_value = ([], None)
            response = self._post_admin(
                "billing_payout_api",
                {"amount": "1500", "card_id": "alien-id"},
            )

        self.assertEqual(response.status_code, 400)

    def test_blacklist_excluded_from_stats(self):
        from shop.models import ExcludedPayer
        from shop.services.billing import get_billing_stats, get_top_payers

        self._make_topup("1000.00", "yoomoney", "card")
        ExcludedPayer.objects.create(telegram_id=111)
        stats = get_billing_stats(days=365)
        self.assertEqual(stats["period"]["gross"], 0.00)
        self.assertEqual(stats["period"]["count"], 0)
        self.assertEqual(get_top_payers(limit=10), [])

    def test_blacklist_api_add_remove(self):
        response = self._post_admin(
            "billing_blacklist_api",
            {"action": "add", "telegram_id": "111"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["blacklisted"], [111])

        self._make_topup("1000.00", "yoomoney", "card")
        response = self._post_admin("billing_api", {"days": "30"})
        self.assertEqual(
            response.json()["stats"]["period"]["gross"],
            0.00,
        )

        response = self._post_admin(
            "billing_blacklist_api",
            {"action": "remove", "telegram_id": "111"},
        )
        self.assertEqual(response.json()["blacklisted"], [])

        response = self._post_admin("billing_api", {"days": "30"})
        self.assertEqual(
            response.json()["stats"]["period"]["gross"],
            1000.00,
        )

    def test_blacklist_api_forbidden(self):
        with patch(
            "shop.views_billing._get_authorized_telegram_id",
        ) as mock_auth:
            mock_auth.return_value = 123
            response = self.client.post(
                reverse("billing_blacklist_api"),
                {"action": "add", "telegram_id": "111"},
            )
            self.assertEqual(response.status_code, 403)

    def test_yoomoney_block_in_stats(self):
        from shop.services.billing import get_billing_stats

        self.mock_yo.return_value = {
            "balance": 1000.0,
            "account_masked": "4100 •••• 6789",
            "error": False,
            "daily": {},
            "total": 0.0,
        }
        stats = get_billing_stats(days=7)
        self.assertEqual(stats["yoomoney"]["balance"], 1000.0)
        self.assertFalse(stats["yoomoney"]["error"])

    def test_wallet_daily_from_history(self):
        from datetime import datetime

        from shop.services.yoomoney import get_wallet_daily

        op1 = MagicMock(
            status="success",
            amount=500.0,
            datetime=datetime(2026, 10, 1, 12, 0),
        )
        op2 = MagicMock(
            status="success",
            amount=200.0,
            datetime=datetime(2026, 10, 1, 15, 0),
        )
        op3 = MagicMock(
            status="canceled",
            amount=999.0,
            datetime=datetime(2026, 10, 1, 16, 0),
        )
        history = MagicMock(operations=[op1, op2, op3], next_record=None)
        old_token = settings.YOOMONEY_TOKEN
        with patch(
            "shop.services.yoomoney.YooClient",
        ) as mock_client_class:
            mock_client_class.return_value.operation_history.return_value = (
                history
            )
            settings.YOOMONEY_TOKEN = "test-token"
            try:
                daily = get_wallet_daily(
                    datetime(2026, 9, 24),
                    datetime(2026, 10, 2),
                )
            finally:
                settings.YOOMONEY_TOKEN = old_token

        self.assertEqual(daily, {"2026-10-01": 700.00})

    def test_account_info_no_token(self):
        from shop.services.yoomoney import get_account_info

        old_token = settings.YOOMONEY_TOKEN
        settings.YOOMONEY_TOKEN = ""
        try:
            self.assertIsNone(get_account_info())
        finally:
            settings.YOOMONEY_TOKEN = old_token

    def test_ledger_create_and_profit(self):
        from datetime import date

        from shop.models import LedgerEntry

        today = date.today().isoformat()
        response = self._post_admin(
            "billing_ledger_api",
            {
                "action": "create",
                "name": "Перевод на карту",
                "amount": "5000",
                "entry_date": today,
            },
        )
        self.assertEqual(response.status_code, 200)
        # Тип по умолчанию на сервере не задан — сумма знающая:
        # положительная прошла как доход
        entry = LedgerEntry.objects.get()
        self.assertEqual(entry.amount, Decimal("5000.00"))

        response = self._post_admin(
            "billing_ledger_api",
            {
                "action": "create",
                "name": "Такси",
                "amount": "-1500",
                "entry_date": today,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ledger"]["total"], 3500.00)
        self.assertEqual(len(data["ledger"]["entries"]), 2)

        response = self._post_admin("billing_api", {"days": "30"})
        self.assertEqual(response.json()["month_profit"], 3500.00)

        response = self._post_admin(
            "billing_ledger_api",
            {"action": "delete", "id": entry.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ledger"]["total"], -1500.00)

    def test_ledger_rejects_zero(self):
        response = self._post_admin(
            "billing_ledger_api",
            {"action": "create", "name": "X", "amount": "0"},
        )
        self.assertEqual(response.status_code, 400)

    def test_topup_stores_payment_method(self):
        with (
            patch(
                "shop.views.verify_telegram_init_data",
            ) as mock_verify,
            patch(
                "shop.views.create_platega_payment",
            ) as mock_create,
        ):
            mock_verify.return_value = (True, {"id": 12345})
            mock_create.return_value = ("https://pay/x", "tx-1")
            settings.PLATEGA_MERCHANT_ID = "m"
            settings.PLATEGA_SECRET = "s"
            Profile.objects.create(telegram_id=12345)
            response = self.client.post(
                reverse("topup_api"),
                {
                    "init_data": "mock",
                    "amount": "300",
                    "payment_provider": "sbp",
                },
            )

        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(platega_transaction_id="tx-1")
        self.assertEqual(order.payment_method, "sbp")
        self.assertEqual(order.payment_provider, "platega")

    def test_payout_signature_format(self):
        import base64
        import hashlib
        import hmac as hmac_lib

        from shop.platega import Platega

        sig = Platega._payout_signature(
            "secret",
            "POST",
            "/api/v1/payouts/card-rub",
            1719403200,
            "idem-1",
            b'{"a":1}',
        )
        sts = "\n".join(
            [
                "POST",
                "/api/v1/payouts/card-rub",
                "1719403200",
                "idem-1",
                hashlib.sha256(b'{"a":1}').hexdigest(),
            ],
        )
        expected = base64.b64encode(
            hmac_lib.new(
                b"secret",
                sts.encode("utf-8"),
                hashlib.sha256,
            ).digest(),
        ).decode("ascii")
        self.assertEqual(sig, expected)

    def test_compute_withdraw_all(self):
        from shop.services.platega_ui import compute_withdraw_all

        # Баланс минус комиссия 0.5 USD по курсу 80
        self.assertEqual(
            compute_withdraw_all(15000.5, 0.5, 80, 1000, 87500),
            14960,
        )
        # Меньше минимума после комиссии — выводить нечего
        self.assertEqual(compute_withdraw_all(500, 0.5, 80, 1000, 87500), 0)
        # Обрезка по максимуму
        self.assertEqual(
            compute_withdraw_all(100000, 0.5, 80, 1000, 87500),
            87460,
        )
        self.assertEqual(compute_withdraw_all(0, 0.5, 80, 1000, 87500), 0)
        self.assertEqual(compute_withdraw_all(None, 0.5, 80, 1000, 87500), 0)

    def test_should_autopayout(self):
        from shop.services.platega_ui import should_autopayout

        self.assertTrue(should_autopayout(15000, 10000, 1000))
        self.assertTrue(should_autopayout(10000, 10000, 1000))
        self.assertFalse(should_autopayout(9999, 10000, 1000))
        # Ниже минимума — нет, даже если порог ниже
        self.assertFalse(should_autopayout(500, 100, 1000))
        self.assertFalse(should_autopayout(None, 10000, 1000))

    def _enable_ui_payout(self):
        old = {
            "secret": settings.PLATEGA_PAYOUT_SECRET,
            "login": settings.PLATEGA_UI_LOGIN,
            "password": settings.PLATEGA_UI_PASSWORD,
            "login_url": settings.PLATEGA_UI_LOGIN_URL,
            "payout_url": settings.PLATEGA_UI_PAYOUT_URL,
            "last4": settings.PLATEGA_PAYOUT_CARD_LAST4,
            "auto": settings.PLATEGA_AUTOPAYOUT_ENABLED,
            "threshold": settings.PLATEGA_AUTOPAYOUT_THRESHOLD_RUB,
        }
        settings.PLATEGA_PAYOUT_SECRET = ""
        settings.PLATEGA_UI_LOGIN = "user"
        settings.PLATEGA_UI_PASSWORD = "pass"
        settings.PLATEGA_UI_LOGIN_URL = "https://cabinet/login"
        settings.PLATEGA_UI_PAYOUT_URL = "https://cabinet/payout"
        settings.PLATEGA_PAYOUT_CARD_LAST4 = "1234"
        settings.PLATEGA_AUTOPAYOUT_ENABLED = False

        def _restore():
            settings.PLATEGA_PAYOUT_SECRET = old["secret"]
            settings.PLATEGA_UI_LOGIN = old["login"]
            settings.PLATEGA_UI_PASSWORD = old["password"]
            settings.PLATEGA_UI_LOGIN_URL = old["login_url"]
            settings.PLATEGA_UI_PAYOUT_URL = old["payout_url"]
            settings.PLATEGA_PAYOUT_CARD_LAST4 = old["last4"]
            settings.PLATEGA_AUTOPAYOUT_ENABLED = old["auto"]
            settings.PLATEGA_AUTOPAYOUT_THRESHOLD_RUB = old["threshold"]

        self.addCleanup(_restore)

    def test_ui_payout_configured(self):
        from shop.services.platega_ui import (
            configured_last4,
            ui_payout_configured,
        )

        self.assertFalse(ui_payout_configured())
        self._enable_ui_payout()
        self.assertTrue(ui_payout_configured())
        self.assertEqual(configured_last4(), "1234")

    def test_billing_api_payout_mode_off(self):
        settings.PLATEGA_PAYOUT_SECRET = ""
        with (
            patch(
                "shop.views_billing.get_platega_balances",
            ) as mock_balances,
            patch(
                "shop.views_billing.get_usd_rub_rate",
                return_value=(80.0, "setting"),
            ),
        ):
            mock_balances.return_value = (
                [
                    {"amount": 15000.5, "currency": "RUB"},
                    {"amount": 200.0, "currency": "USDT"},
                ],
                None,
            )
            response = self._post_admin("billing_api", {"days": "30"})

        data = response.json()
        self.assertEqual(data["payout_mode"], "off")
        self.assertEqual(data["payout_min"], 1000)
        self.assertEqual(data["payout_max"], 87500)
        self.assertEqual(data["payout_fee_usd"], 0.5)
        # «Вывести всё» — из USDT после холда: 200*80 - 40.
        # RUB-баланс (холд) не считаем.
        self.assertEqual(data["payout_all_amount"], 15960)
        self.assertEqual(data["usd_rub_rate"], 80.0)
        self.assertEqual(data["usd_rub_rate_source"], "setting")
        self.assertIsNone(data["payout_dest_masked"])
        self.assertFalse(data["autopayout"]["enabled"])

    def test_usd_rub_rate_er_api(self):
        from shop.services.billing import get_usd_rub_rate

        with patch("shop.services.billing.requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"rates": {"RUB": 82.5}}
            rate, source = get_usd_rub_rate()

        self.assertEqual(rate, 82.5)
        self.assertEqual(source, "er-api")

    def test_usd_rub_rate_cbr_fallback(self):
        from shop.services.billing import get_usd_rub_rate

        def _fake_get(url, timeout):
            response = MagicMock()
            if "er-api" in url:
                raise Exception("down")

            response.json.return_value = {"Valute": {"USD": {"Value": 81.25}}}
            return response

        with patch(
            "shop.services.billing.requests.get",
            side_effect=_fake_get,
        ):
            rate, source = get_usd_rub_rate()

        self.assertEqual(rate, 81.25)
        self.assertEqual(source, "cbr")

    def test_usd_rub_rate_setting_fallback(self):
        from shop.services.billing import get_usd_rub_rate

        with patch(
            "shop.services.billing.requests.get",
            side_effect=Exception("down"),
        ):
            rate, source = get_usd_rub_rate()

        self.assertEqual(source, "setting")
        self.assertTrue(rate > 0)

    def test_billing_payout_api_ui_queue(self):
        from shop.models import PayoutJob

        self._enable_ui_payout()
        response = self._post_admin("billing_payout_api", {"amount": "1500"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["mode"], "ui")
        job = PayoutJob.objects.get(id=data["job_id"])
        self.assertEqual(job.status, PayoutJob.STATUS_QUEUED)
        self.assertEqual(job.mode, PayoutJob.MODE_MANUAL)
        self.assertEqual(float(job.amount), 1500.0)
        self.assertEqual(job.dest_last4, "1234")

    def test_billing_payout_api_ui_max(self):
        from shop.models import PayoutJob

        self._enable_ui_payout()
        response = self._post_admin(
            "billing_payout_api",
            {"amount": "0", "is_max": "1"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["mode"], "ui")
        job = PayoutJob.objects.get(id=data["job_id"])
        self.assertTrue(job.is_max)
        self.assertEqual(float(job.amount), 0.0)

    def test_parse_usdt_amount(self):
        from shop.services.platega_ui import _parse_usdt_amount

        self.assertEqual(
            _parse_usdt_amount("Доступно к выводу 3.31 USDT"),
            3.31,
        )
        self.assertEqual(_parse_usdt_amount("3,31 USDT"), 3.31)
        self.assertEqual(
            _parse_usdt_amount("Ваш баланс 1 250.50 USDT"),
            1250.5,
        )
        self.assertIsNone(_parse_usdt_amount("денег нет"))
        self.assertIsNone(_parse_usdt_amount(""))
        self.assertIsNone(_parse_usdt_amount(None))

    def test_billing_payout_api_ui_busy(self):
        from shop.models import PayoutJob

        self._enable_ui_payout()
        PayoutJob.objects.create(
            amount=Decimal("1500"),
            dest_last4="1234",
            mode=PayoutJob.MODE_MANUAL,
        )
        response = self._post_admin("billing_payout_api", {"amount": "1500"})
        self.assertEqual(response.status_code, 429)

    def test_billing_payout_job_api(self):
        from shop.models import PayoutJob

        self._enable_ui_payout()
        job = PayoutJob.objects.create(
            amount=Decimal("2000"),
            dest_last4="1234",
            mode=PayoutJob.MODE_MANUAL,
            status=PayoutJob.STATUS_DONE,
            result={"status": "DONE", "page_text": "ok"},
        )
        response = self._post_admin(
            "billing_payout_job_api",
            {"job_id": str(job.id)},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "DONE")
        self.assertEqual(data["amount"], 2000.0)
        self.assertEqual(data["dest_masked"], "**** 1234")
        self.assertEqual(data["page_text"], "ok")

        response = self._post_admin(
            "billing_payout_job_api",
            {"job_id": "999999"},
        )
        self.assertEqual(response.status_code, 404)

    def test_schedule_auto_job(self):
        from shop.models import PayoutJob
        from shop.services import payout_worker

        self._enable_ui_payout()
        settings.PLATEGA_AUTOPAYOUT_ENABLED = True
        settings.PLATEGA_AUTOPAYOUT_THRESHOLD_RUB = 10000
        with (
            patch.object(
                payout_worker,
                "get_withdrawable_rub",
                return_value=(15000.0, None),
            ),
            patch.object(
                payout_worker,
                "get_usd_rub_rate",
                return_value=(80.0, "setting"),
            ),
        ):
            job = payout_worker.schedule_auto_job()

        self.assertIsNotNone(job)
        self.assertEqual(job.mode, PayoutJob.MODE_AUTO)
        self.assertTrue(job.is_max)
        self.assertEqual(float(job.amount), 14960.0)

    def test_schedule_auto_job_below_threshold(self):
        from shop.services import payout_worker

        self._enable_ui_payout()
        settings.PLATEGA_AUTOPAYOUT_ENABLED = True
        settings.PLATEGA_AUTOPAYOUT_THRESHOLD_RUB = 10000
        with (
            patch.object(
                payout_worker,
                "get_withdrawable_rub",
                return_value=(5000.0, None),
            ),
            patch.object(
                payout_worker,
                "get_usd_rub_rate",
                return_value=(80.0, "setting"),
            ),
        ):
            self.assertIsNone(payout_worker.schedule_auto_job())

    def test_schedule_auto_job_cooldown(self):
        from shop.models import PayoutJob
        from shop.services import payout_worker

        self._enable_ui_payout()
        settings.PLATEGA_AUTOPAYOUT_ENABLED = True
        settings.PLATEGA_AUTOPAYOUT_THRESHOLD_RUB = 10000
        PayoutJob.objects.create(
            amount=Decimal("15000"),
            dest_last4="1234",
            mode=PayoutJob.MODE_AUTO,
            status=PayoutJob.STATUS_DONE,
        )
        with (
            patch.object(
                payout_worker,
                "get_withdrawable_rub",
                return_value=(50000.0, None),
            ),
            patch.object(
                payout_worker,
                "get_usd_rub_rate",
                return_value=(80.0, "setting"),
            ),
        ):
            self.assertIsNone(payout_worker.schedule_auto_job())


class PayoutWorkerTests(TransactionTestCase):
    """Исполнение заявок: воркер работает в потоках, поэтому обычный
    TestCase не подходит (транзакция теста не видна из потоков)."""

    def _run_job(self, bot, job):
        import asyncio
        from asgiref.sync import sync_to_async
        from django.db import connections

        from shop.services import payout_worker

        async def _run():
            try:
                return await payout_worker.execute_job(bot, 999, job)
            finally:
                # Соединения потоков воркера — закрыть, иначе teardown
                # тестовой БД упрётся в «accessed by other users».
                await sync_to_async(connections.close_all)()

        return asyncio.run(_run())

    def test_execute_job_success(self):
        from unittest.mock import AsyncMock

        from shop.models import Order, PayoutJob
        from shop.services import payout_worker

        job = PayoutJob.objects.create(
            amount=Decimal("1500"),
            dest_last4="1234",
            mode=PayoutJob.MODE_MANUAL,
            status=PayoutJob.STATUS_RUNNING,
        )
        sent = []

        class FakeBot:
            async def send_message(self, chat_id, text):
                sent.append(text)

            async def send_photo(self, chat_id, photo, caption=None):
                sent.append(caption or "")

        with patch.object(
            payout_worker,
            "run_ui_card_payout",
            new=AsyncMock(
                return_value={
                    "status": "DONE",
                    "amount_rub": 1500,
                    "page_text": "ok",
                    "shots": [],
                },
            ),
        ):
            self._run_job(FakeBot(), job)

        job.refresh_from_db()
        self.assertEqual(job.status, PayoutJob.STATUS_DONE)
        payout = Order.objects.get(order_type="PAYOUT")
        self.assertEqual(float(payout.amount), 1500.0)
        self.assertTrue(any("1500" in m for m in sent))

    def test_execute_job_max_uses_actual_amount(self):
        from unittest.mock import AsyncMock

        from shop.models import Order, PayoutJob
        from shop.services import payout_worker

        job = PayoutJob.objects.create(
            amount=Decimal("0"),
            is_max=True,
            dest_last4="1234",
            mode=PayoutJob.MODE_MANUAL,
            status=PayoutJob.STATUS_RUNNING,
        )
        sent = []

        class FakeBot:
            async def send_message(self, chat_id, text):
                sent.append(text)

            async def send_photo(self, chat_id, photo, caption=None):
                sent.append(caption or "")

        with patch.object(
            payout_worker,
            "run_ui_card_payout",
            new=AsyncMock(
                return_value={
                    "status": "DONE",
                    "amount_rub": 0,
                    "actual_amount_rub": 1300,
                    "site_available_usdt": 16.5,
                    "page_text": "ok",
                    "shots": [],
                },
            ),
        ):
            self._run_job(FakeBot(), job)

        job.refresh_from_db()
        self.assertEqual(job.status, PayoutJob.STATUS_DONE)
        self.assertEqual(float(job.amount), 1300.0)
        self.assertTrue(job.is_max)
        payout = Order.objects.get(order_type="PAYOUT")
        self.assertEqual(float(payout.amount), 1300.0)
        self.assertTrue(any("1300" in m for m in sent))

    def test_execute_job_failure(self):
        from unittest.mock import AsyncMock

        from shop.models import PayoutJob
        from shop.services import payout_worker
        from shop.services.platega_ui import UiPayoutError

        job = PayoutJob.objects.create(
            amount=Decimal("1500"),
            dest_last4="1234",
            mode=PayoutJob.MODE_MANUAL,
            status=PayoutJob.STATUS_RUNNING,
        )
        sent = []

        class FakeBot:
            async def send_message(self, chat_id, text):
                sent.append(text)

            async def send_photo(self, chat_id, photo, caption=None):
                sent.append(caption or "")

        with patch.object(
            payout_worker,
            "run_ui_card_payout",
            new=AsyncMock(side_effect=UiPayoutError("site error: bad")),
        ):
            self._run_job(FakeBot(), job)

        job.refresh_from_db()
        self.assertEqual(job.status, PayoutJob.STATUS_FAILED)
        self.assertIn("site error", job.error)
        self.assertTrue(any("не удался" in m for m in sent))
