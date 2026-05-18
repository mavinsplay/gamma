from django.db import models

__all__ = ()


class Proxy(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название прокси")
    server = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Сервер (host)",
    )
    port = models.IntegerField(null=True, blank=True, verbose_name="Порт")
    secret = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Секрет (для MTProxy)",
    )
    connection_url = models.TextField(
        verbose_name="Ссылка для подключения",
        help_text=(
            "Например: https://t.me/proxy?" "server=...&port=...&secret=..."
        ),
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Описание",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proxy"
        verbose_name_plural = "Proxies"

    def __str__(self):
        return self.name


class NodeStatus(models.Model):
    node_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="ID Ноды (Remnawave)",
    )
    status_text = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Статус сервера",
    )
    use_manual_status = models.BooleanField(
        default=False,
        verbose_name="Ручное управление",
    )
    manual_is_online = models.BooleanField(
        default=True,
        verbose_name="Статус онлайн (вручную)",
    )

    class Meta:
        verbose_name = "Статус сервера"
        verbose_name_plural = "Статусы серверов"

    def __str__(self):
        return f"Node {self.node_id}: {self.status_text}"
