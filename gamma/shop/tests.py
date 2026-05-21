import json
import hashlib
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from django.conf import settings

from shop.models import Order, Tariff
from user.models import Profile

class PaymentSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.profile = Profile.objects.create(telegram_id=12345, balance=Decimal("100.00"))
        self.tariff = Tariff.objects.create(name="Test Tariff", price=Decimal("150.00"), duration_days=30, traffic_limit_bytes=1000, device_limit=1)
        
        # Override settings for tests
        settings.PALLY_API_KEY = "test_key"
        settings.DEBUG = False # Ensure we test production auth logic

    @patch('shop.views.verify_telegram_init_data')
    @patch('shop.views.requests.post')
    def test_topup_api_creates_pending_order(self, mock_post, mock_verify):
        # Mock auth
        mock_verify.return_value = (True, {"id": 12345, "username": "testuser"})
        
        # Mock Pally API response
        mock_post.return_value.json.return_value = {"link_page_url": "https://pally.info/transfer/xyz"}
        mock_post.return_value.raise_for_status = lambda: None
        
        # Call API
        response = self.client.post(reverse('topup_api'), {"tg_id": "12345", "amount": "500", "init_data": "mock_data"})
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["payment_url"], "https://pally.info/transfer/xyz")
        
        # Ensure balance did NOT increase instantly
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("100.00"))
        
        # Ensure PENDING order was created
        order = Order.objects.get(telegram_id=12345, amount=Decimal("500.00"))
        self.assertEqual(order.status, "PENDING")

    def test_pally_webhook_valid_signature(self):
        order = Order.objects.create(telegram_id=12345, amount=Decimal("500.00"), order_type="TOPUP", status="PENDING")
        
        payload = {
            "Status": "SUCCESS",
            "InvId": str(order.id),
            "OutSum": "500.00"
        }
        
        sign_string = f"500.00:{order.id}:test_key"
        signature = hashlib.md5(sign_string.encode('utf-8')).hexdigest().upper()
        payload["SignatureValue"] = signature
        
        response = self.client.post(
            reverse('pally_webhook_api'),
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        
        # Check if balance was updated and order PAID
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("600.00"))
        
        order.refresh_from_db()
        self.assertEqual(order.status, "PAID")

    def test_pally_webhook_invalid_signature(self):
        order = Order.objects.create(telegram_id=12345, amount=Decimal("500.00"), order_type="TOPUP", status="PENDING")
        
        payload = {
            "Status": "SUCCESS",
            "InvId": str(order.id),
            "OutSum": "500.00",
            "SignatureValue": "FAKE_SIGNATURE"
        }
        
        response = self.client.post(
            reverse('pally_webhook_api'),
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Invalid signature")
        
        # Check balance did NOT increase
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("100.00"))
        
        order.refresh_from_db()
        self.assertEqual(order.status, "PENDING")

    @patch('shop.views.verify_telegram_init_data')
    def test_buy_tariff_insufficient_funds(self, mock_verify):
        # User has 100, tariff is 150
        mock_verify.return_value = (True, {"id": 12345, "username": "testuser"})
        
        response = self.client.post(reverse('buy_tariff_api'), {
            "tg_id": "12345",
            "tariff_id": self.tariff.id,
            "init_data": "mock_data"
        })
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "insufficient_funds")
        
        # Balance should remain unchanged
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("100.00"))

    @patch('shop.views.verify_telegram_init_data')
    def test_topup_api_debug_instant_credit(self, mock_verify):
        """In DEBUG mode, topup should credit balance immediately."""
        mock_verify.return_value = (True, {"id": 12345, "username": "testuser"})
        settings.DEBUG = True

        response = self.client.post(reverse('topup_api'), {
            "tg_id": "12345",
            "amount": "200",
            "init_data": "mock_data"
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["new_balance"], 300.0)

        # Balance credited instantly
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal("300.00"))

        # Order created as PAID
        order = Order.objects.get(
            telegram_id=12345, amount=Decimal("200.00")
        )
        self.assertEqual(order.status, "PAID")

        # Reset DEBUG for other tests
        settings.DEBUG = False
