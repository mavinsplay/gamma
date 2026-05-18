from django.contrib import admin
from .models import Tariff, Order, PromoCode, PromoCodeUsage


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "device_limit",
        "has_proxy_bypass",
        "is_active",
    )
    list_filter = ("is_active", "has_proxy_bypass")
    search_fields = ("name", "description")
    list_editable = ("price", "is_active", "has_proxy_bypass")
    filter_horizontal = ("proxies",)


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
