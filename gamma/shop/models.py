from django.db import models

__all__ = [
    "Tariff",
    "Order",
    "PromoCode",
    "PromoCodeUsage",
]


class Tariff(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30)
    traffic_limit_bytes = models.BigIntegerField(
        default=0,
    )  # 0 means unlimited
    device_limit = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    squad_uuid = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    has_whitelist = models.BooleanField(
        default=False,
        verbose_name="VPN с обходом белых списков",
    )
    whitelist_squad_uuid = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Whitelist Squad UUID",
        help_text=(
            "Squad UUID для whitelist-подписки (обход белых списков). "
            "Заполнять только если has_whitelist=True."
        ),
    )
    proxies = models.ManyToManyField(
        "connect.Proxy",
        blank=True,
        verbose_name="Доступные прокси",
        related_name="tariffs",
    )

    def __str__(self):
        return f"{self.name} - {self.price} RUB"


class Order(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
        ("CHARGEBACK", "Chargeback"),
    )
    TYPE_CHOICES = (
        ("PURCHASE", "Purchase"),
        ("TOPUP", "Top-up"),
        ("WHITELIST_TOPUP", "Whitelist Traffic Top-up"),
    )
    PROVIDER_CHOICES = (
        ("yoomoney", "YooMoney"),
        ("platega", "Platega"),
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    telegram_id = models.BigIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    order_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="PURCHASE",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    payment_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default="yoomoney",
        verbose_name="Платёжный провайдер",
    )
    platega_transaction_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Platega Transaction ID",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.status}"


class PromoCode(models.Model):
    REWARD_CHOICES = (
        ("BALANCE", "Баланс"),
        ("DAYS", "Дни подписки"),
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Промокод",
    )
    reward_type = models.CharField(
        max_length=10,
        choices=REWARD_CHOICES,
        verbose_name="Тип награды",
    )
    reward_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма (₽) / Дни",
        help_text="Сумма в рублях для BALANCE, количество дней для DAYS",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    def __str__(self):
        return (
            f"{self.code} — "
            f"{self.get_reward_type_display()} {self.reward_value}"
        )

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"


class PromoCodeUsage(models.Model):
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.CASCADE,
        related_name="usages",
    )
    profile = models.ForeignKey(
        "user.Profile",
        on_delete=models.CASCADE,
        related_name="promo_usages",
    )
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.promo_code.code} — {self.profile}"

    class Meta:
        unique_together = ("promo_code", "profile")
        verbose_name = "Использование промокода"
        verbose_name_plural = "Использования промокодов"
