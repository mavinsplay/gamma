from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "telegram_username", "balance", "tarif", "created_at")
    search_fields = ("telegram_id", "telegram_username")
    list_filter = ("tarif", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
