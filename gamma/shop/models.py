from django.db import models


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

    def __str__(self):
        return f"{self.name} - {self.price} RUB"


class Order(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("FAILED", "Failed"),
    )
    tariff = models.ForeignKey(Tariff, on_delete=models.SET_NULL, null=True)
    telegram_id = models.BigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.status}"
