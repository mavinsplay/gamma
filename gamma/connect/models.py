from django.db import models

class Proxy(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название прокси")
    server = models.CharField(max_length=255, null=True, blank=True, verbose_name="Сервер (host)")
    port = models.IntegerField(null=True, blank=True, verbose_name="Порт")
    secret = models.CharField(max_length=255, null=True, blank=True, verbose_name="Секрет (для MTProxy)")
    connection_url = models.TextField(
        verbose_name="Ссылка для подключения",
        help_text="Например: https://t.me/proxy?server=...&port=...&secret=..."
    )
    description = models.TextField(null=True, blank=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proxy"
        verbose_name_plural = "Proxies"

    def __str__(self):
        return self.name
