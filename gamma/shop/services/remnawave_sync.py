from datetime import datetime, timedelta, timezone
import logging

from django.conf import settings

from connect.services.remnawave import match_wl_id, RemnawaveClient, user_ref

logger = logging.getLogger(__name__)

__all__ = ["sync_tariff_to_remnawave", "sync_whitelist_user"]


def _as_users(response):
    if isinstance(response, dict):
        return response.get("users", [response] if response else [])

    return response or []


def _get_main_user(rw_users, profile=None):
    stored = getattr(profile, "whitelist_uuid", None)
    return next(
        (
            user
            for user in _as_users(rw_users)
            if user_ref(user)
            and not (user.get("username") or "").endswith("_wl")
            and not match_wl_id(user, stored)
        ),
        None,
    )


def _username(profile, whitelist=False):
    suffix = f"_{profile.telegram_id}" + ("_wl" if whitelist else "")
    prefix = profile.telegram_username or "user"
    prefix = (
        "".join(
            c for c in prefix if c.isascii() and (c.isalnum() or c in "_-")
        )
        or "user"
    )
    return prefix[: 36 - len(suffix)] + suffix


async def sync_whitelist_user(
    client,
    profile,
    tariff,
    main_user,
    users,
    reset_limits=False,
):
    """Use the main expiry exactly; an update failure is never a create."""
    users = _as_users(users)
    whitelist = next(
        (
            user
            for user in users
            if user_ref(user) != user_ref(main_user)
            and (
                match_wl_id(user, profile.whitelist_uuid)
                or (user.get("username") or "").endswith("_wl")
            )
        ),
        None,
    )
    if not tariff or not tariff.has_whitelist:
        if whitelist:
            await client.update_user(
                uuid=user_ref(whitelist),
                status="DISABLED",
            )

        return None

    if not tariff.whitelist_squad_uuid:
        raise ValueError("У тарифа не настроен whitelist squad")

    expire_at = main_user.get("expireAt")
    if not expire_at:
        raise ValueError("У основной подписки отсутствует срок действия")

    expiry = datetime.fromisoformat(expire_at.replace("Z", "+00:00"))
    active = (
        expiry > datetime.now(timezone.utc)
        and main_user.get("status") != "DISABLED"
    )
    changes = {
        "expire_at": expire_at,
        "status": "ACTIVE" if active else "DISABLED",
        "activeinternalsquads": [tariff.whitelist_squad_uuid],
        "externalsquaduuid": settings.WHITELIST_EXTERNAL_SQUAD_UUID,
    }
    if not whitelist or reset_limits:
        changes.update(
            trafficlimitbytes=5368709120,
            trafficlimitstrategy="MONTH",
            hwiddevicelimit=20,
        )

    if whitelist:
        await client.update_user(uuid=user_ref(whitelist), **changes)
        return {
            **whitelist,
            "expireAt": expire_at,
            "status": changes["status"],
        }

    username = (main_user.get("username") or "") + "_wl"
    if len(username) > 36 or len(username) < 6:
        username = _username(profile, whitelist=True)

    whitelist = await client.create_user(
        username=username,
        days=0,
        telegramid=int(profile.telegram_id),
        **changes,
    )
    if not whitelist or not user_ref(whitelist):
        raise ValueError("Remnawave не вернул идентификатор созданного _wl")

    return whitelist


async def sync_tariff_to_remnawave(profile, tariff, client=None):
    own_client = client is None
    client = client or RemnawaveClient()
    try:
        users = _as_users(await client.get_user_by_tgid(profile.telegram_id))
        main = _get_main_user(users, profile)
        if tariff is None:
            for user in users:
                await client.update_user(
                    uuid=user_ref(user),
                    status="DISABLED",
                )

            return main, None

        if tariff.has_whitelist and not tariff.whitelist_squad_uuid:
            raise ValueError("У тарифа не настроен whitelist squad")

        expire_at = (
            (datetime.now(timezone.utc) + timedelta(days=tariff.duration_days))
            .isoformat()
            .replace("+00:00", "Z")
        )
        changes = {
            "expire_at": expire_at,
            "status": "ACTIVE",
            "trafficlimitbytes": tariff.traffic_limit_bytes,
            "hwiddevicelimit": tariff.device_limit,
            "activeinternalsquads": (
                [tariff.squad_uuid] if tariff.squad_uuid else []
            ),
        }
        if main:
            updated = await client.update_user(uuid=user_ref(main), **changes)
        else:
            updated = await client.create_user(
                username=_username(profile),
                days=tariff.duration_days,
                telegramid=int(profile.telegram_id),
                **changes,
            )

        updated = {
            **(main or {}),
            **updated,
            "expireAt": expire_at,
            "status": "ACTIVE",
        }
        try:
            whitelist = await sync_whitelist_user(
                client,
                profile,
                tariff,
                updated,
                users,
                reset_limits=True,
            )
        except Exception:
            # Compensate the main change before the caller refunds payment.
            try:
                if main:
                    await client.update_user(
                        uuid=user_ref(main),
                        expire_at=main.get("expireAt"),
                        status=(
                            "ACTIVE"
                            if main.get("status") == "ACTIVE"
                            else "DISABLED"
                        ),
                        trafficlimitbytes=main.get("trafficLimitBytes"),
                        hwiddevicelimit=main.get("hwidDeviceLimit"),
                        activeinternalsquads=[
                            s.get("uuid") if isinstance(s, dict) else s
                            for s in main.get("activeInternalSquads", [])
                        ],
                    )
                else:
                    await client.update_user(
                        uuid=user_ref(updated),
                        status="DISABLED",
                    )
            except Exception:
                logger.exception(
                    "Failed to restore subscription for %s",
                    profile.telegram_id,
                )

            raise

        return updated, user_ref(whitelist) if whitelist else None
    finally:
        if own_client:
            await client.close()
