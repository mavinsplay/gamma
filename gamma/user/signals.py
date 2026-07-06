import logging

from asgiref.sync import async_to_sync
from django.db.models.signals import post_delete
from django.dispatch import receiver

from connect.services.remnawave import RemnawaveClient
from user.models import Profile

__all__ = ()

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=Profile)
def delete_remnawave_user(sender, instance, **kwargs):
    """
    Automatically disable the user in Remnawave when their
    Profile is deleted.
    """
    telegram_id = instance.telegram_id

    async def _disable_async():
        client = RemnawaveClient()
        try:
            rw_users = await client.get_user_by_tgid(telegram_id)

            if isinstance(rw_users, list):
                for u in rw_users:
                    if u and u.get("uuid"):
                        try:
                            await client.update_user(
                                uuid=u["uuid"],
                                status="DISABLED",
                            )
                        except Exception:
                            pass
            elif rw_users and rw_users.get("uuid"):
                await client.update_user(
                    uuid=rw_users["uuid"],
                    status="DISABLED",
                )
        except Exception as e:
            logger.error(
                "Error disabling Remnawave user for" " telegram_id %s: %s",
                telegram_id,
                e,
            )
        finally:
            await client.close()

    try:
        async_to_sync(_disable_async)()
    except Exception as e:
        logger.error(
            "Failed to execute Remnawave disable task: %s",
            e,
        )
