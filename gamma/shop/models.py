from django.db import models

__all__ = [
    "Tariff",
    "Order",
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
    has_proxy_bypass = models.BooleanField(
        default=False,
        verbose_name="Proxy",
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
    )
    TYPE_CHOICES = (
        ("PURCHASE", "Purchase"),
        ("TOPUP", "Top-up"),
    )
    tariff = models.ForeignKey(
        Tariff, on_delete=models.SET_NULL, null=True, blank=True
    )
    telegram_id = models.BigIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    order_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default="PURCHASE"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.status}"
