from django.db import migrations

# Kept as literals rather than imported from the models: a migration has to
# keep working when the code moves on, and these are the values as they were
# on the day it ran.
PURCHASE_SETTLED = {"approved", "rejected"}
IMPORT_SETTLED = {"agreed", "cancelled"}


def raise_tickets(apps, schema_editor):
    """Tickets replace the Approvals and Sourcing queues, so everything those
    queues held has to exist as a ticket - otherwise the day this ships, live
    work disappears from the screens staff use.

    Settled requests get a closed ticket rather than none: the ticket is the
    record of the work, and a closed one keeps the history readable.
    """
    Ticket = apps.get_model("tickets", "Ticket")
    PurchaseRequest = apps.get_model("purchases", "PurchaseRequest")
    ImportRequest = apps.get_model("imports", "ImportRequest")

    Ticket.objects.bulk_create(
        [
            Ticket(
                kind="approval",
                purchase_request=request,
                status="closed" if request.status in PURCHASE_SETTLED else "open",
            )
            for request in PurchaseRequest.objects.filter(ticket__isnull=True)
        ]
    )
    Ticket.objects.bulk_create(
        [
            Ticket(
                kind="sourcing",
                import_request=request,
                status="closed" if request.status in IMPORT_SETTLED else "open",
            )
            for request in ImportRequest.objects.filter(ticket__isnull=True)
        ]
    )


def drop_tickets(apps, schema_editor):
    apps.get_model("tickets", "Ticket").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(raise_tickets, drop_tickets),
    ]
