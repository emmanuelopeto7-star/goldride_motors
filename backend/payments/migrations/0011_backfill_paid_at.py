"""Give existing paid payments a paid_at.

There is no record of when they were paid: the only timestamps on the row are
created_at (when the invoice was raised) and updated_at (last touched by
anything). updated_at is the closer of the two - for most of these the paid
transition was the last thing that happened to the row - so it is the best
evidence available, and freezing it here stops it drifting any further.

Approximate for old rows, exact for every row after this. Anything already
carrying a paid_at is left alone.
"""

from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    Payment.objects.filter(status="paid", paid_at__isnull=True).update(
        paid_at=F("updated_at")
    )


def unbackfill(apps, schema_editor):
    # Reversing drops the approximation rather than pretending it was data.
    Payment = apps.get_model("payments", "Payment")
    Payment.objects.update(paid_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0010_payment_paid_at"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
