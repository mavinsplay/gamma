from django.db import models

__all__ = [
    "Profile",
]


class Profile(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    telegram_username = models.CharField(
        max_length=100,
        null=True,
        default=None,
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
    )
    tarif = models.ForeignKey(
        "shop.Tariff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    payment_reminder_enabled = models.BooleanField(
        default=True,
        verbose_name="Напоминание об оплате",
    )
    notifications_enabled = models.BooleanField(
        default=True,
        verbose_name="Уведомления",
    )
    subscription_expired_notification_sent = models.BooleanField(
        default=False,
        verbose_name="Уведомление об окончании подписки отправлено",
    )
    # Whitelist bypass subscription (separate Remnawave user)
    whitelist_uuid = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Whitelist UUID в Remnawave",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile {self.telegram_id} - {self.balance} RUB"
