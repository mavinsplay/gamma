from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0011_profile_server_notifications_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="telegram_avatar_url",
            field=models.URLField(
                blank=True,
                max_length=500,
                null=True,
                verbose_name="Аватар Telegram",
            ),
        ),
    ]
