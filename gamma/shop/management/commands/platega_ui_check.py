"""Проверка браузерного вывода: логин + шаги без отправки заявки."""

import asyncio

from django.core.management.base import BaseCommand, CommandError

from shop.services.platega_ui import run_ui_card_payout, UiPayoutError

__all__ = ("Command",)


class Command(BaseCommand):
    help = (  # noqa: A003 — стандартное поле Django-команд
        "Логинится в кабинет Platega и проходит форму вывода "
        "без нажатия отправки (dry_run). Пишет скриншоты шагов."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--amount",
            type=int,
            default=1000,
            help="Сумма для заполнения формы (не отправляется)",
        )

    def handle(self, *args, **options):
        try:
            result = asyncio.run(
                run_ui_card_payout(
                    options["amount"],
                    dry_run=True,
                ),
            )
        except UiPayoutError as e:
            raise CommandError(f"UI check failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"UI check OK: {result}"))
