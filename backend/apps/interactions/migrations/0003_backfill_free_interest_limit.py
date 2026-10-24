"""
Mark existing interests that count toward the Free package's 15-interest limit:
those sent while the sender had no active subscription covering the send date.
Interests sent during a paid subscription never count.
"""
from django.db import migrations
from django.db.models import Exists, OuterRef


def forwards(apps, schema_editor):
    Interest = apps.get_model("interactions", "Interest")
    Subscription = apps.get_model("memberships", "Subscription")

    paid_at_send = Subscription.objects.filter(
        user=OuterRef("sender__user"),
        status="active",
        starts_at__lte=OuterRef("created_at"),
        ends_at__gt=OuterRef("created_at"),
    )
    Interest.objects.filter(~Exists(paid_at_send)).update(counts_toward_free_limit=True)


class Migration(migrations.Migration):
    dependencies = [
        ("interactions", "0002_free_interest_limit_and_contact_views"),
        ("memberships", "0003_seed_packages_and_backfill_subscription_terms"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
