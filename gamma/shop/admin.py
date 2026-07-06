from django.contrib import admin

from shop.models import Order, PromoCode, PromoCodeUsage, Tariff

__all__ = ()


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "device_limit",
        "has_whitelist",
        "is_active",
    )
    list_filter = ("is_active", "has_whitelist")
    search_fields = ("name", "description")
    list_editable = ("price", "is_active", "has_whitelist")
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
                )
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
    list_display = ("id", "tariff", "telegram_id", "status", "created_at")
    list_filter = ("status", "created_at", "tariff")
    search_fields = ("telegram_id",)
    readonly_fields = ("created_at",)
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
