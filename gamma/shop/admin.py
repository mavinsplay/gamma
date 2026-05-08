from django.contrib import admin
from .models import Tariff, Order

@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "duration_days", "device_limit", "has_proxy_bypass", "is_active")
    list_filter = ("is_active", "has_proxy_bypass")
    search_fields = ("name", "description")
    list_editable = ("price", "is_active", "has_proxy_bypass")

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "tariff", "telegram_id", "status", "created_at")
    list_filter = ("status", "created_at", "tariff")
    search_fields = ("telegram_id",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
