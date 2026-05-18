from django.apps import AppConfig

__all__ = ()


class UserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "user"

    def ready(self):
        import user.signals  # noqa: F401
