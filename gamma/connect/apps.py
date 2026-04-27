from django.apps import AppConfig

__all__ = ["ConnectConfig"]


class ConnectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "connect"
