from django.db import migrations


def backfill_payment_method(apps, schema_editor):
    """Старые TOPUP без метода: platega -> sbp, yoomoney -> card."""
    Order = apps.get_model("shop", "Order")
    Order.objects.filter(
        order_type="TOPUP",
        payment_method="",
        payment_provider="platega",
    ).update(payment_method="sbp")
    Order.objects.filter(
        order_type="TOPUP",
        payment_method="",
        payment_provider="yoomoney",
    ).update(payment_method="card")


def noop_reverse(apps, schema_editor):
    # Исходные пустые значения восстановить нельзя — односторонняя.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0024_payoutjob_is_max"),
    ]

    operations = [
        migrations.RunPython(backfill_payment_method, noop_reverse),
    ]
