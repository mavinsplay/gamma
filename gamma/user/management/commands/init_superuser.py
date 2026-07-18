import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from dotenv import load_dotenv

__all__ = ()


class Command(BaseCommand):

    load_dotenv()

    def handle(self, *args, **options):
        superuser_name = os.getenv("SUPERUSER_NAME", "admin")
        superuser_email = os.getenv(
            "SUPERUSER_EMAIL",
            "admin@gamma.ru",
        )
        user_exists = (
            get_user_model()
            .objects.filter(
                username=superuser_name,
            )
            .exists()
        )
        superuser_password = os.getenv("SUPERUSER_PASSWORD")

        if not user_exists:
            if not superuser_password:
                raise ValueError(
                    "SUPERUSER_PASSWORD must be set to create a superuser.",
                )

            get_user_model().objects.create_superuser(
                username=superuser_name,
                email=superuser_email,
                password=superuser_password,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "Superuser created successfully!\n"
                    f"USERNAME: {superuser_name}",
                ),
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Superuser already exists!\n"
                    f"USERNAME: {superuser_name}",
                ),
            )
