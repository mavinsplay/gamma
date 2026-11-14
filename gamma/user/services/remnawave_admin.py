from datetime import datetime, timedelta, timezone

from connect.services.remnawave import (
    match_wl_id,
    RemnawaveClient,
    user_ref,
)
from shop.services.remnawave_sync import sync_whitelist_user

__all__ = [
    "change_subscription_days",
    "ensure_whitelist_sync",
    "get_all_subscription_statuses",
    "get_subscription_sync_status",
]


def _as_users(response):
    if not response:
        return []

    if isinstance(response, list):
        return response

    if isinstance(response, dict):
        # 3.x заворачивает в TelegramUserResponseDto {users: [...]}.
        inner = response.get("users")
        if isinstance(inner, list):
            return inner

        return [response]

    return []


def _parse_expire_at(user):
    value = user.get("expireAt")
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _find_users(users, profile):
    main_user = next(
        (
            u
            for u in users
            if not (u.get("username") or "").endswith("_wl")
            and not match_wl_id(u, profile.whitelist_uuid)
        ),
        None,
    )
    if profile.whitelist_uuid:
        whitelist_user = next(
            (u for u in users if match_wl_id(u, profile.whitelist_uuid)),
            None,
        )
        if whitelist_user is None:
            # Сохранённый id устарел (2.x uuid) — ищем по суффиксу.
            whitelist_user = next(
                (u for u in users if u.get("username", "").endswith("_wl")),
                None,
            )
    else:
        whitelist_user = next(
            (u for u in users if u.get("username", "").endswith("_wl")),
            None,
        )

    return main_user, whitelist_user


async def change_subscription_days(profile, days):
    client = RemnawaveClient()
    try:
        users = _as_users(await client.get_user_by_tgid(profile.telegram_id))
        main_user, whitelist_user = _find_users(users, profile)
        if main_user is None:
            raise ValueError("Основной пользователь не найден в Remnawave")

        now = datetime.now(timezone.utc)
        base_expire_at = max(_parse_expire_at(main_user) or now, now)
        new_expire_at = base_expire_at + timedelta(days=days)
        if new_expire_at <= now:
            raise ValueError("Нельзя установить срок в прошлом")

        updates = [
            (user, new_expire_at.isoformat().replace("+00:00", "Z"))
            for user in (main_user, whitelist_user)
            if user is not None
        ]

        for user, expire_at in updates:
            await client.update_user(
                uuid=user_ref(user),
                expire_at=expire_at,
                status="ACTIVE",
            )

        return main_user, whitelist_user, len(updates)
    finally:
        await client.close()


async def ensure_whitelist_sync(profile, tariff=None):
    client = RemnawaveClient()
    try:
        users = _as_users(await client.get_user_by_tgid(profile.telegram_id))
        main_user, whitelist_user = _find_users(users, profile)
        if main_user is None:
            raise ValueError("Основной пользователь не найден в Remnawave")

        tariff = tariff or profile._state.fields_cache.get("tarif")
        if not tariff or not tariff.has_whitelist:
            raise ValueError("В текущем тарифе нет обхода белых списков")

        return await sync_whitelist_user(
            client,
            profile,
            tariff,
            main_user,
            users,
        )
    finally:
        await client.close()


async def get_subscription_sync_status(profile):
    client = RemnawaveClient()
    try:
        users = _as_users(await client.get_user_by_tgid(profile.telegram_id))
        main_user, whitelist_user = _find_users(users, profile)
        now = datetime.now(timezone.utc)

        def details(user):
            if user is None:
                return None

            expire_at = _parse_expire_at(user)
            remaining_days = max(0, (expire_at - now).days) if expire_at else 0
            return {
                "uuid": user_ref(user),
                "username": user.get("username"),
                "status": user.get("status"),
                "expire_at": expire_at,
                "remaining_days": remaining_days,
            }

        return {
            "main": details(main_user),
            "whitelist": details(whitelist_user),
            "whitelist_uuid": profile.whitelist_uuid,
            "users_count": len(users),
        }

    finally:
        await client.close()


async def get_all_subscription_statuses():
    client = RemnawaveClient()
    try:
        users = []
        start = 0
        size = 500
        while True:
            response = await client.get_users(size=size, start=start)
            if isinstance(response, dict):
                page = response.get("users", [])
                total = response.get("total")
            else:
                page = response or []
                total = None

            users.extend(page)
            if not page or (total is not None and len(users) >= total):
                break

            start += len(page)

        now = datetime.now(timezone.utc)
        grouped = {}
        for user in users:
            telegram_id = user.get("telegramId")
            if telegram_id is None:
                continue

            key = str(telegram_id)
            grouped.setdefault(key, []).append(user)

        statuses = {}
        for telegram_id, telegram_users in grouped.items():
            main_user = next(
                (
                    user
                    for user in telegram_users
                    if not user.get("username", "").endswith("_wl")
                ),
                telegram_users[0],
            )
            expire_at = _parse_expire_at(main_user)
            remaining_days = max(0, (expire_at - now).days) if expire_at else 0
            statuses[telegram_id] = {
                "remaining_days": remaining_days,
                "active": remaining_days > 0,
                "status": "ACTIVE" if remaining_days > 0 else "EXPIRED",
            }

        return statuses
    finally:
        await client.close()
