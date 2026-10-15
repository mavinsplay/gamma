from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from shop.models import Tariff
from user.models import Profile
from user.services.remnawave_admin import (
    change_subscription_days,
    ensure_whitelist_sync,
    get_all_subscription_statuses,
    get_subscription_sync_status,
)

__all__ = (
    "RemnawaveAdminServiceTests",
    "AvatarUrlProxyTests",
)


class RemnawaveAdminServiceTests(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(
            telegram_id=5976619850,
            whitelist_uuid="wl-uuid",
        )
        self.tariff = Tariff.objects.create(
            name="Whitelist tariff",
            price=100,
            duration_days=30,
            has_whitelist=True,
            whitelist_squad_uuid="wl-squad",
        )

    @patch("user.services.remnawave_admin.RemnawaveClient")
    def test_add_days_reactivates_main_and_whitelist(self, client_class):
        client = client_class.return_value
        client.get_user_by_tgid = AsyncMock(
            return_value=[
                {
                    "uuid": "main-uuid",
                    "username": "user",
                    "status": "EXPIRED",
                    "expireAt": "2020-01-01T00:00:00.000Z",
                },
                {
                    "uuid": "wl-uuid",
                    "username": "user_wl",
                    "status": "EXPIRED",
                    "expireAt": "2020-01-01T00:00:00.000Z",
                },
            ],
        )
        client.update_user = AsyncMock()
        client.close = AsyncMock()

        result = async_to_sync(change_subscription_days)(self.profile, 30)

        self.assertEqual(result[2], 2)
        self.assertEqual(client.update_user.await_count, 2)
        for call in client.update_user.await_args_list:
            self.assertEqual(call.kwargs["status"], "ACTIVE")
            self.assertGreater(
                datetime.fromisoformat(
                    call.kwargs["expire_at"].replace("Z", "+00:00"),
                ),
                datetime.now(timezone.utc),
            )

    @patch("user.services.remnawave_admin.RemnawaveClient")
    def test_sync_status_reports_zero_days_for_expired_whitelist(
        self,
        client_class,
    ):
        client = client_class.return_value
        client.get_user_by_tgid = AsyncMock(
            return_value=[
                {
                    "uuid": "main-uuid",
                    "username": "user",
                    "status": "ACTIVE",
                    "expireAt": "2020-01-01T00:00:00.000Z",
                },
                {
                    "uuid": "wl-uuid",
                    "username": "user_wl",
                    "status": "EXPIRED",
                    "expireAt": "2020-01-01T00:00:00.000Z",
                },
            ],
        )
        client.close = AsyncMock()

        result = async_to_sync(get_subscription_sync_status)(self.profile)

        self.assertEqual(result["main"]["remaining_days"], 0)
        self.assertEqual(result["whitelist"]["remaining_days"], 0)

    @patch("user.services.remnawave_admin.RemnawaveClient")
    def test_ensure_whitelist_creates_missing_user(self, client_class):
        self.profile.tarif = self.tariff
        self.profile.save(update_fields=["tarif"])
        client = client_class.return_value
        client.get_user_by_tgid = AsyncMock(
            return_value=[
                {
                    "uuid": "main-uuid",
                    "username": "user",
                    "status": "ACTIVE",
                    "expireAt": "2020-01-01T00:00:00.000Z",
                },
            ],
        )
        client.create_user = AsyncMock(
            return_value={"uuid": "new-wl-uuid", "username": "user_wl"},
        )
        client.close = AsyncMock()

        result = async_to_sync(ensure_whitelist_sync)(
            self.profile,
            self.tariff,
        )

        self.assertEqual(result["uuid"], "new-wl-uuid")
        client.create_user.assert_awaited_once()
        self.assertEqual(
            client.create_user.await_args.kwargs["activeinternalsquads"],
            ["wl-squad"],
        )

    @patch("user.services.remnawave_admin.RemnawaveClient")
    def test_all_statuses_use_one_users_request(self, client_class):
        client = client_class.return_value
        client.get_users = AsyncMock(
            return_value={
                "users": [
                    {
                        "telegramId": 5976619850,
                        "username": "user",
                        "expireAt": "2020-01-01T00:00:00.000Z",
                    },
                ],
                "total": 1,
            },
        )
        client.close = AsyncMock()

        result = async_to_sync(get_all_subscription_statuses)()

        self.assertEqual(result["5976619850"]["status"], "EXPIRED")
        client.get_users.assert_awaited_once_with(size=500, start=0)


class AvatarUrlProxyTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        self.client = Client()
        # Кэш (Redis) общий между прогонами — чистим, иначе тесты
        # находят чужие закэшированные аватарки.
        cache.clear()
        self._old_admin = settings.ADMIN_TELEGRAM_ID
        settings.ADMIN_TELEGRAM_ID = 999
        self.addCleanup(self._restore_settings)

    def _restore_settings(self):
        settings.ADMIN_TELEGRAM_ID = self._old_admin

    def _get(self, tg_id, url):
        with patch(
            "user.views._get_authorized_telegram_id",
        ) as mock_auth:
            mock_auth.return_value = tg_id
            return self.client.get(reverse("avatar_url_proxy"), {"url": url})

    def test_forbidden_for_non_admin(self):
        response = self._get(123, "https://t.me/i/userpic/1.jpg")
        self.assertEqual(response.status_code, 403)

    def test_staff_allowed_without_telegram_auth(self):
        from django.contrib.auth.models import User

        staff = User.objects.create_user(username="boss", is_staff=True)
        self.client.force_login(staff)
        fake = MagicMock()
        fake.headers = {"Content-Type": "image/jpeg"}
        fake.content = b"staff-bytes"
        with patch("user.views.requests.get", return_value=fake):
            response = self.client.get(
                reverse("avatar_url_proxy"),
                {"url": "https://t.me/i/userpic/9.jpg"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"staff-bytes")

    def test_rejects_non_https_and_foreign_hosts(self):
        for bad in (
            "http://t.me/i/userpic/1.jpg",
            "https://evil.com/avatar.jpg",
            "https://sub.evil.com/x.jpg",
            "not-a-url",
            "",
        ):
            response = self._get(999, bad)
            self.assertEqual(response.status_code, 204)

    def test_proxies_telegram_cdn_and_caches(self):
        fake = MagicMock()
        fake.headers = {"Content-Type": "image/jpeg"}
        fake.content = b"fake-bytes"
        with patch("user.views.requests.get", return_value=fake) as mock_get:
            first = self._get(999, "https://t.me/i/userpic/1.jpg")
            second = self._get(999, "https://t.me/i/userpic/1.jpg")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.content, b"fake-bytes")
        self.assertEqual(first["Content-Type"], "image/jpeg")
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(second.content, b"fake-bytes")

    def test_rejects_non_image_and_oversize(self):
        fake = MagicMock()
        fake.headers = {"Content-Type": "text/html"}
        fake.content = b"<html>"
        with patch("user.views.requests.get", return_value=fake):
            response = self._get(999, "https://t.me/i/userpic/2.jpg")

        self.assertEqual(response.status_code, 204)

        big = MagicMock()
        big.headers = {"Content-Type": "image/jpeg"}
        big.content = b"x" * (2 * 1024 * 1024 + 1)
        with patch("user.views.requests.get", return_value=big):
            response = self._get(
                999,
                "https://cdn-telegram.org/pic.jpg",
            )

        self.assertEqual(response.status_code, 204)
