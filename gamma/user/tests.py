from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import TestCase

from shop.models import Tariff
from user.models import Profile
from user.services.remnawave_admin import (
    change_subscription_days,
    ensure_whitelist_sync,
    get_all_subscription_statuses,
    get_subscription_sync_status,
)

__all__ = ("RemnawaveAdminServiceTests",)


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
