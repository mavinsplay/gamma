import logging
from asgiref.sync import async_to_sync
from django.db.models.signals import post_delete
from django.dispatch import receiver
from connect.services.remnawave import RemnawaveClient
from .models import Profile

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
                    f"Successfully deleted Remnawave user for telegram_id {telegram_id} (UUID: {user_uuid})"
                )
            else:
                logger.warning(
                    f"No Remnawave user found for telegram_id {telegram_id}, skipping deletion."
                )
        except Exception as e:
            logger.error(
                f"Error while deleting Remnawave user for telegram_id {telegram_id}: {e}"
            )
        finally:
            await client.close()

    try:
        # RemnawaveClient uses async httpx, so we use async_to_sync to call it from the signal
        async_to_sync(_delete_async)()
    except Exception as e:
        logger.error(f"Failed to execute Remnawave deletion task: {e}")
