from datetime import datetime, timedelta, timezone
import logging

from connect.services.remnawave import RemnawaveClient

logger = logging.getLogger(__name__)

__all__ = ["sync_tariff_to_remnawave"]


def _get_main_user(rw_users, profile=None):
    """Filter out whitelist users, returning only the main user."""
    if not isinstance(rw_users, list):
        return rw_users

    wl_uuid = getattr(profile, "whitelist_uuid", None) if profile else None

    for u in rw_users:
        if u and u.get("uuid"):
            if wl_uuid and u["uuid"] == wl_uuid:
                continue

            if u.get("username", "").endswith("_wl"):
                continue

            return u

    return rw_users[0] if rw_users else None


async def sync_tariff_to_remnawave(profile, tariff, client=None):
    """Sync tariff assignment to Remnawave.

    Mirrors the logic from buy_tariff_api (replace_sub + provision_new)
    but without balance deduction or Order creation.

    Returns (rw_data, whitelist_uuid) or raises on failure.
    """
    own_client = client is None
    if own_client:
        client = RemnawaveClient()

    try:
        telegram_id = profile.telegram_id
        cur_whitelist_uuid = profile.whitelist_uuid

        # Fetch existing RW users
        rw_users = await client.get_user_by_tgid(telegram_id)
        if not isinstance(rw_users, list):
            rw_users = [rw_users] if rw_users else []

        rw_user = _get_main_user(rw_users, profile)

        # --- Try replace_sub first (update existing user) ---
        if rw_user and rw_user.get("uuid"):
            try:
                new_expire = (
                    (
                        datetime.now(timezone.utc)
                        + timedelta(days=tariff.duration_days)
                    )
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                main_squads = [tariff.squad_uuid] if tariff.squad_uuid else []

                await client.update_user(
                    uuid=rw_user["uuid"],
                    expire_at=new_expire,
                    trafficlimitbytes=tariff.traffic_limit_bytes,
                    hwiddevicelimit=tariff.device_limit,
                    activeinternalsquads=main_squads,
                )

                # Handle whitelist sub
                whitelist_uuid = None
                if tariff.has_whitelist and tariff.whitelist_squad_uuid:
                    # Re-enable existing whitelist user
                    if cur_whitelist_uuid:
                        try:
                            await client.update_user(
                                uuid=cur_whitelist_uuid,
                                expire_at=new_expire,
                                status="ACTIVE",
                                trafficlimitbytes=5368709120,
                                hwiddevicelimit=20,
                                activeinternalsquads=[
                                    tariff.whitelist_squad_uuid,
                                ],
                            )
                            whitelist_uuid = cur_whitelist_uuid
                        except Exception:
                            pass

                    # Find existing disabled _wl user
                    if not whitelist_uuid:
                        for u in rw_users:
                            uname = u.get("username", "")
                            if uname.endswith("_wl") and u.get(
                                "uuid",
                            ) != rw_user.get("uuid"):
                                try:
                                    await client.update_user(
                                        uuid=u["uuid"],
                                        expire_at=new_expire,
                                        trafficlimitbytes=5368709120,
                                        hwiddevicelimit=20,
                                        status="ACTIVE",
                                        activeinternalsquads=[
                                            tariff.whitelist_squad_uuid,
                                        ],
                                    )
                                    whitelist_uuid = u["uuid"]
                                except Exception:
                                    pass

                                break

                    # Create new whitelist user if nothing found
                    if not whitelist_uuid:
                        try:
                            wl_user = await client.create_user(
                                username=(
                                    f"{rw_user.get('username', str(telegram_id))}" # noqa
                                    "_wl"
                                ),
                                days=tariff.duration_days,
                                trafficlimitbytes=5368709120,
                                hwiddevicelimit=20,
                                telegramid=int(telegram_id),
                                activeinternalsquads=[
                                    tariff.whitelist_squad_uuid,
                                ],
                            )
                            if wl_user and wl_user.get("uuid"):
                                whitelist_uuid = wl_user["uuid"]
                        except Exception:
                            pass
                else:
                    # New tariff has no whitelist — disable old _wl user
                    if cur_whitelist_uuid:
                        try:
                            await client.update_user(
                                uuid=cur_whitelist_uuid,
                                status="DISABLED",
                            )
                        except Exception:
                            pass

                return rw_user, whitelist_uuid

            except Exception:
                logger.warning(
                    "replace_sub failed for tg_id=%s, "
                    "falling back to provision_new",
                    telegram_id,
                )

        # --- Fallback: provision_new (create fresh user) ---
        username = f"{profile.telegram_username or 'user'}_{telegram_id}"
        main_squads = [tariff.squad_uuid] if tariff.squad_uuid else []

        # Disable ALL existing users with this telegramId
        for u in rw_users:
            if u and u.get("uuid"):
                try:
                    await client.update_user(
                        uuid=u["uuid"],
                        status="DISABLED",
                    )
                except Exception:
                    pass

        main_user = await client.create_user(
            username=username,
            days=tariff.duration_days,
            trafficlimitbytes=tariff.traffic_limit_bytes,
            hwiddevicelimit=tariff.device_limit,
            telegramid=int(telegram_id),
            activeinternalsquads=main_squads,
        )

        # Provision whitelist sub if tariff supports it
        whitelist_uuid = None
        if tariff.has_whitelist and tariff.whitelist_squad_uuid:
            # Try to find existing disabled _wl user first
            for u in rw_users:
                uname = u.get("username", "")
                if uname.endswith("_wl"):
                    try:
                        await client.update_user(
                            uuid=u["uuid"],
                            expire_at=(
                                main_user.get("expireAt")
                                if main_user
                                else None
                            ),
                            trafficlimitbytes=5368709120,
                            hwiddevicelimit=20,
                            status="ACTIVE",
                            activeinternalsquads=[tariff.whitelist_squad_uuid],
                        )
                        whitelist_uuid = u["uuid"]
                    except Exception:
                        pass

                    break

            if not whitelist_uuid:
                try:
                    wl_user = await client.create_user(
                        username=f"{username}_wl",
                        days=tariff.duration_days,
                        trafficlimitbytes=5368709120,
                        hwiddevicelimit=20,
                        telegramid=int(telegram_id),
                        activeinternalsquads=[tariff.whitelist_squad_uuid],
                    )
                    if wl_user and wl_user.get("uuid"):
                        whitelist_uuid = wl_user["uuid"]
                except Exception:
                    pass

        return main_user, whitelist_uuid

    finally:
        if own_client:
            await client.close()
