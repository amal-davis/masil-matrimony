"""
Give every purchase recorded before status history existed one history entry
with its current payment status, so the history never starts empty. Changes
no purchase.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Purchase = apps.get_model("payments", "Purchase")
    PurchaseEvent = apps.get_model("payments", "PurchaseEvent")
    events = [
        PurchaseEvent(
            purchase=purchase, status=purchase.status, refund_status=purchase.refund_status, source="system",
            note="Status when history began; earlier changes weren't recorded.",
        )
        for purchase in Purchase.objects.filter(events__isnull=True)
    ]
    PurchaseEvent.objects.bulk_create(events)


class Migration(migrations.Migration):
    dependencies = [("payments", "0002_purchase_refunds_and_history")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
