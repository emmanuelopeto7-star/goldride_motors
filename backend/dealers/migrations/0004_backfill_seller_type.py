"""Every seller that existed before the split was a dealership.

`seller_type` defaults to "individual", which is right for the field going
forward and wrong for every row already in the table: applying was a thing only
dealerships could do until today. Left alone, a real dealership would quietly
be relabelled a private seller and lose its trading name on every screen.

Rows with no dealership_name are left as they are - there should be none, but
guessing at one would be worse than the default.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    DealerApplication = apps.get_model("dealers", "DealerApplication")
    Dealer = apps.get_model("dealers", "Dealer")

    DealerApplication.objects.exclude(dealership_name="").update(
        seller_type="dealer"
    )
    Dealer.objects.filter(application__isnull=False).update(seller_type="dealer")
    Dealer.objects.filter(application__isnull=True).update(seller_type="dealer")


def unbackfill(apps, schema_editor):
    # Reversing drops the distinction rather than pretending to know it.
    apps.get_model("dealers", "DealerApplication").objects.update(
        seller_type="individual"
    )
    apps.get_model("dealers", "Dealer").objects.update(seller_type="individual")


class Migration(migrations.Migration):

    dependencies = [
        ("dealers", "0003_remove_dealer_website_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
