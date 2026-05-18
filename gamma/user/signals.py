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
    Automatically delete the user from Remnawave when their Profile is deleted.
    """
    telegram_id = instance.telegram_id

    async def _delete_async():
        client = RemnawaveClient()
        try:
            # Find the user in Remnawave by their Telegram ID
            rw_user = await client.get_user_by_tgid(telegram_id)

            # The API might return a list or a single user object
            if isinstance(rw_user, list):
                rw_user = rw_user[0] if len(rw_user) > 0 else None

            if rw_user and rw_user.get("uuid"):
                user_uuid = rw_user["uuid"]
                await client.delete_user(user_uuid)
                logger.info(
                    "Successfully deleted Remnawave user for"
                    " telegram_id %s (UUID: %s)",
                    telegram_id,
                    user_uuid,
                )
            else:
                logger.warning(
                    "No Remnawave user found for telegram_id"
                    " %s, skipping deletion.",
                    telegram_id,
                )
        except Exception as e:
            logger.error(
                "Error deleting Remnawave user for" " telegram_id %s: %s",
                telegram_id,
                e,
            )
        finally:
            await client.close()

    try:
        # RemnawaveClient is async, so use async_to_sync from the signal
        async_to_sync(_delete_async)()
    except Exception as e:
        logger.error(
            "Failed to execute Remnawave deletion task: %s",
            e,
        )
