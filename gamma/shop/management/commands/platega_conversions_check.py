"""Read-only check of the authenticated Platega conversion history."""

import asyncio

from django.core.management.base import BaseCommand, CommandError

from shop.services.conversion_monitor import read_ui_conversions

__all__ = ("Command",)


class Command(BaseCommand):
    help = (  # noqa: A003
        "Проверяет чтение завершённых конвертаций Platega. "
        "Не отправляет уведомления и не изменяет деньги или историю проверки."
    )

    def handle(self, *args, **options):
        try:
            conversions = asyncio.run(
                asyncio.wait_for(read_ui_conversions(), timeout=180),
            )
        except Exception as error:
            raise CommandError(
                f"Не удалось прочитать конвертации ({type(error).__name__}). "
                "Проверьте доступ к кабинету и структуру таблицы.",
            ) from None

        self.stdout.write(
            self.style.SUCCESS(
                f"Завершённых конвертаций прочитано: {len(conversions)}",
            ),
        )
