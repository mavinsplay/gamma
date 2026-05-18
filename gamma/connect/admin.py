from django.contrib import admin

from connect.models import Proxy

__all__ = ()


@admin.register(Proxy)
class ProxyAdmin(admin.ModelAdmin):
    list_display = ("name", "server", "port", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "server", "connection_url", "description")
    list_editable = ("is_active",)
