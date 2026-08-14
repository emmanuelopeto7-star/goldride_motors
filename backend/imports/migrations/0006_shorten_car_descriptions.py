"""Rewrite the car_description blobs left behind by the old Car.__str__.

Approval used to store `str(car)`, which trailed the entire sales description
and priced the car in dollars. Three consequences, all live:

  * it renders as the <h1> on the public tracking page
  * it reaches customers in email subject lines through ImportOrder.__str__
  * it overflows this column - the field is varchar(200) and the longest
    stored value is 246 characters. SQLite ignores that; Postgres does not,
    so approving a car with a long description raised DataError in production.

Orders with no car keep whatever was typed, truncated to fit.
"""

from django.db import migrations


def shorten(apps, schema_editor):
    ImportOrder = apps.get_model('imports', 'ImportOrder')

    for order in ImportOrder.objects.select_related('car').iterator():
        if order.car_id:
            car = order.car
            replacement = f"{car.year} {car.make} {car.model}"
        elif len(order.car_description or "") > 200:
            replacement = order.car_description[:200]
        else:
            continue

        if replacement != order.car_description:
            order.car_description = replacement
            order.save(update_fields=['car_description'])


def noop(apps, schema_editor):
    # Irreversible by nature: the old value was derived from fields that have
    # since changed, so it cannot be reconstructed. Declared so the migration
    # can still be rolled back past.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('imports', '0005_importorder_cancel_reason_importorder_cancelled_at_and_more'),
    ]

    operations = [
        migrations.RunPython(shorten, noop),
    ]
