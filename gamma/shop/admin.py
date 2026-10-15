from django.contrib import admin

from shop.models import (
    BillingSetting,
    ExcludedPayer,
    LedgerEntry,
    Order,
    PayoutJob,
    PromoCode,
    PromoCodeUsage,
    ServerExpense,
    Tariff,
)

__all__ = ()


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "device_limit",
        "has_whitelist",
        "change_locked",
        "is_active",
    )
    list_filter = ("is_active", "has_whitelist", "change_locked")
    search_fields = ("name", "description")
    list_editable = ("price", "is_active", "has_whitelist", "change_locked")
    filter_horizontal = ("proxies",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "description",
                    "price",
                    "duration_days",
                    "traffic_limit_bytes",
                    "device_limit",
                    "is_active",
                    "change_locked",
                ),
            },
        ),
        (
            "Remnawave",
            {
                "fields": ("squad_uuid",),
            },
        ),
        (
            "Proxy / Whitelist",
            {
                "fields": (
                    "has_whitelist",
                    "whitelist_squad_uuid",
                    "proxies",
                ),
                "description": (
                    "Если has_whitelist=True — заполните "
                    "whitelist_squad_uuid. "
                    "Пользователю создаётся отдельная "
                    "whitelist-подписка (5 ГБ)."
                ),
            },
        ),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tariff",
        "telegram_id",
        "status",
        "order_type",
        "payment_provider",
        "payment_method",
        "amount",
        "created_at",
    )
    list_filter = (
        "status",
        "order_type",
        "payment_provider",
        "payment_method",
        "created_at",
        "tariff",
    )
    search_fields = ("telegram_id",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(ServerExpense)
class ServerExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "monthly_cost",
        "pay_day",
        "last_paid",
        "created_at",
    )
    list_filter = ("pay_day",)
    search_fields = ("name",)
    readonly_fields = ("created_at",)
    ordering = ("pay_day", "name")


@admin.register(ExcludedPayer)
class ExcludedPayerAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "note", "created_at")
    search_fields = ("telegram_id", "note")
    readonly_fields = ("created_at",)
    ordering = ("telegram_id",)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "entry_date", "created_at")
    list_filter = ("entry_date",)
    search_fields = ("name",)
    readonly_fields = ("created_at",)
    ordering = ("-entry_date", "-id")


@admin.register(BillingSetting)
class BillingSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "updated_at")
    search_fields = ("key",)
    readonly_fields = ("updated_at",)
    ordering = ("key",)


@admin.register(PayoutJob)
class PayoutJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "amount",
        "dest_last4",
        "mode",
        "status",
        "created_at",
    )
    list_filter = ("mode", "status")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "reward_type",
        "reward_value",
        "is_active",
        "created_at",
    )
    list_filter = ("reward_type", "is_active")
    search_fields = ("code",)
    list_editable = ("is_active",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(PromoCodeUsage)
class PromoCodeUsageAdmin(admin.ModelAdmin):
    list_display = ("promo_code", "profile", "used_at")
    list_filter = ("promo_code", "used_at")
    search_fields = ("promo_code__code", "profile__telegram_username")
    readonly_fields = ("used_at",)
    ordering = ("-used_at",)
