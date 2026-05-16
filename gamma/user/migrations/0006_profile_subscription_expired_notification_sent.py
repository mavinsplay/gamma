from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0005_profile_notifications_enabled_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='subscription_expired_notification_sent',
            field=models.BooleanField(default=False, verbose_name='Уведомление об окончании подписки отправлено'),
        ),
    ]