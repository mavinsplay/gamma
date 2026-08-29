from datetime import datetime, timedelta, timezone
from math import ceil

from django.conf import settings

from connect.services.remnawave import RemnawaveClient

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

    return [response]


def _parse_expire_at(user):
    value = user.get("expireAt")
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _find_users(users, profile):
    main_user = next(
        (u for u in users if not u.get("username", "").endswith("_wl")),
        None,
    )
    if profile.whitelist_uuid:
        whitelist_user = next(
            (u for u in users if u.get("uuid") == profile.whitelist_uuid),
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
        updates = []
        for user in (main_user, whitelist_user):
            if user is None:
                continue

            expire_at = _parse_expire_at(user) or now
            base_expire_at = max(expire_at, now)
            new_expire_at = base_expire_at + timedelta(days=days)
            if new_expire_at <= now:
                raise ValueError(
                    "Нельзя установить срок в прошлом или ровно сейчас",
                )

            updates.append(
                (
                    user,
                    new_expire_at.isoformat().replace("+00:00", "Z"),
                ),
            )

        for user, expire_at in updates:
            await client.update_user(
                uuid=user["uuid"],
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

        if whitelist_user is None:
            whitelist_user = next(
                (u for u in users if u.get("username", "").endswith("_wl")),
                None,
            )

        if whitelist_user is not None:
            return whitelist_user

        tariff = tariff or profile._state.fields_cache.get("tarif")
        if not tariff or not tariff.has_whitelist:
            raise ValueError("У текущего тарифа не включён _wl доступ")

        if not tariff.whitelist_squad_uuid:
            raise ValueError("У тарифа не настроен whitelist squad")

        now = datetime.now(timezone.utc)
        expire_at = _parse_expire_at(main_user)
        remaining_days = (
            ceil((expire_at - now).total_seconds() / 86400)
            if expire_at and expire_at > now
            else tariff.duration_days
        )
        whitelist_user = await client.create_user(
            username=f"{main_user.get('username', profile.telegram_id)}_wl",
            days=max(1, remaining_days),
            trafficlimitbytes=5368709120,
            trafficlimitstrategy="MONTH",
            hwiddevicelimit=20,
            telegramid=int(profile.telegram_id),
            activeinternalsquads=[tariff.whitelist_squad_uuid],
            status="ACTIVE",
            externalsquaduuid=getattr(
                settings,
                "WHITELIST_EXTERNAL_SQUAD_UUID",
                "68fce704-b469-43f4-afc9-8a38a5c8b851",
            ),
        )
        if not whitelist_user or not whitelist_user.get("uuid"):
            raise ValueError("Remnawave не вернул UUID созданного _wl")

        return whitelist_user
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
                "uuid": user.get("uuid"),
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
