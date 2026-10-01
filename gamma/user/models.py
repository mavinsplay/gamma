import secrets
import string

from django.db import models

__all__ = [
    "Profile",
    "ensure_referral_code",
    "generate_referral_code",
]


def generate_referral_code(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ensure_referral_code(profile):
    """Выдать профилю уникальный реферальный код (лениво)."""
    if profile.referral_code:
        return profile.referral_code

    for _ in range(10):
        code = generate_referral_code()
        if not Profile.objects.filter(referral_code=code).exists():
            profile.referral_code = code
            profile.save(update_fields=["referral_code"])
            return code

    raise ValueError("Не удалось сгенерировать реферальный код.")


class Profile(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    telegram_username = models.CharField(
        max_length=100,
        null=True,
        default=None,
    )
    telegram_avatar_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Аватар Telegram",
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
    server_notifications_enabled = models.BooleanField(
        default=True,
        verbose_name="Уведомления о серверах",
    )
    # Whitelist bypass subscription (separate Remnawave user)
    whitelist_uuid = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Whitelist UUID в Remnawave",
    )
    # Реферальная система
    referral_code = models.CharField(
        max_length=16,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Реферальный код",
    )
    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="referrals",
        verbose_name="Пригласил",
    )
    referral_reward_paid = models.BooleanField(
        default=False,
        verbose_name="Реферальная награда выплачена",
    )
    referral_earned = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Заработано по рефералам",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile {self.telegram_id} - {self.balance} RUB"
