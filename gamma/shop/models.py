from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

__all__ = [
    "Tariff",
    "Order",
    "PromoCode",
    "PromoCodeUsage",
    "ServerExpense",
    "ExcludedPayer",
    "LedgerEntry",
]

# Награда пригласившему за первую покупку подписки рефералом (₽).
REFERRAL_REWARD = Decimal("100.00")


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
    change_locked = models.BooleanField(
        default=False,
        verbose_name="Блокировка смены тарифа",
        help_text=(
            "Если включено — пользователь с этим тарифом "
            "не сможет сменить его на другой."
        ),
    )
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
        ("SLOT", "Slot"),
        ("REFERRAL", "Referral"),
        ("PAYOUT", "Payout"),
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
    bonus_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Бонус (₽)",
        help_text="+4% за СБП/крипту: баллы сверху, доходом не считается",
    )
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
    METHOD_CHOICES = (
        ("card", "Card"),
        ("sbp", "SBP"),
        ("crypto", "Crypto"),
    )
    payment_method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        default="",
        blank=True,
        verbose_name="Метод оплаты",
        help_text="card — карта (YooMoney), sbp/crypto — Platega",
    )
    platega_transaction_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Platega Transaction ID",
    )
    payment_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="URL оплаты",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.status}"


class ServerExpense(models.Model):
    """Ежемесячные расходы админа на сервера (для биллинга)."""

    name = models.CharField(
        max_length=100,
        verbose_name="Сервер",
    )
    monthly_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Стоимость в месяц (₽)",
    )
    pay_day = models.IntegerField(
        verbose_name="День оплаты",
        help_text="Число месяца (1–31), когда нужно платить",
        validators=[MinValueValidator(1), MaxValueValidator(31)],
    )
    last_paid = models.DateField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Последняя оплата",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} — {self.monthly_cost} ₽/мес"

    class Meta:
        verbose_name = "Расход на сервер"
        verbose_name_plural = "Расходы на сервера"
        ordering = ("pay_day", "name")


class PayoutJob(models.Model):
    """Заявка на вывод через браузер (Payout API не одобрен).

    Создаётся из панели (вручную) или автопорогом, исполняется
    фоновой задачей бота через Playwright. PAN карты здесь не храним —
    только последние 4 цифры; сам номер — в .env.
    """

    STATUS_QUEUED = "QUEUED"
    STATUS_RUNNING = "RUNNING"
    STATUS_DONE = "DONE"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "В очереди"),
        (STATUS_RUNNING, "Выполняется"),
        (STATUS_DONE, "Выполнен"),
        (STATUS_FAILED, "Ошибка"),
    )
    MODE_MANUAL = "manual"
    MODE_AUTO = "auto"
    MODE_CHOICES = (
        (MODE_MANUAL, "Вручную"),
        (MODE_AUTO, "Автопорог"),
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма (₽)",
    )
    is_max = models.BooleanField(
        default=False,
        verbose_name="Максимум с сайта",
        help_text="Точную сумму определяет сайт (баланс минус курс "
        "и комиссия), amount — лишь оценка для отображения",
    )
    dest_last4 = models.CharField(
        max_length=4,
        default="",
        blank=True,
        verbose_name="Карта (посл. 4 цифры)",
    )
    mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        default=MODE_MANUAL,
        verbose_name="Режим",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
        verbose_name="Статус",
    )
    result = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Результат",
    )
    error = models.TextField(
        default="",
        blank=True,
        verbose_name="Ошибка",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Вывод {self.amount} ₽ — {self.get_status_display()}"

    class Meta:
        verbose_name = "Заявка на вывод"
        verbose_name_plural = "Заявки на вывод"
        ordering = ("-created_at",)


class BillingSetting(models.Model):
    """Настройки билинг-панели (key-value), правятся из интерфейса."""

    key = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Ключ",
    )
    value = models.TextField(
        default="",
        blank=True,
        verbose_name="Значение",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key} = {self.value}"

    class Meta:
        verbose_name = "Настройка биллинга"
        verbose_name_plural = "Настройки биллинга"
        ordering = ("key",)


class ExcludedPayer(models.Model):
    """Тестовые/служебные плательщики, скрытые из билинг-статистики."""

    telegram_id = models.BigIntegerField(
        unique=True,
        verbose_name="Telegram ID",
    )
    note = models.CharField(
        max_length=100,
        default="",
        blank=True,
        verbose_name="Заметка",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Excluded {self.telegram_id}"

    class Meta:
        verbose_name = "Скрытый плательщик"
        verbose_name_plural = "Скрытые плательщики"
        ordering = ("telegram_id",)


class LedgerEntry(models.Model):
    """Разовая запись в плюс/минус (внеплановые доходы и расходы)."""

    name = models.CharField(
        max_length=100,
        verbose_name="Описание",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма (₽)",
        help_text="Плюс — доход (напр. перевод на карту), минус — расход",
    )
    entry_date = models.DateField(
        verbose_name="Дата",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        sign = "+" if self.amount >= 0 else ""
        return f"{self.name} — {sign}{self.amount} ₽"

    class Meta:
        verbose_name = "Запись учёта"
        verbose_name_plural = "Учёт доходов/расходов"
        ordering = ("-entry_date", "-id")


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
