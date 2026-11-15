"""Read-only check of the Platega USDT balance API."""

from django.core.management.base import BaseCommand, CommandError

from shop.services.conversion_monitor import read_usdt_balance

__all__ = ("Command",)


class Command(BaseCommand):
    help = (  # noqa: A003
        "Читает баланс USDT через API без отправки уведомлений "
        "и без изменения сохранённого значения."
    )

    def handle(self, *args, **options):
        try:
            balance = read_usdt_balance()
        except ValueError as error:
            raise CommandError(str(error)) from None

        self.stdout.write(self.style.SUCCESS(f"Баланс: {balance:.2f} USDT"))
