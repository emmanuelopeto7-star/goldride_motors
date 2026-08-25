from django.db import migrations


def raise_tickets(apps, schema_editor):
    """Enquiries that arrived before the queue knew about them.

    They were sitting on a read-only screen with no record of whether anyone
    had answered, which is the gap this kind closes. Unanswered ones become
    open tickets so they are actually picked up.
    """
    Ticket = apps.get_model("tickets", "Ticket")
    Inquiry = apps.get_model("inquiries", "Inquiry")

    Ticket.objects.bulk_create(
        [
            Ticket(
                kind="enquiry",
                inquiry=inquiry,
                status="closed" if inquiry.replied_at else "open",
            )
            for inquiry in Inquiry.objects.filter(ticket__isnull=True)
        ]
    )


def drop_tickets(apps, schema_editor):
    apps.get_model("tickets", "Ticket").objects.filter(kind="enquiry").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0003_remove_ticket_ticket_subject_matches_kind_and_more"),
        ("inquiries", "0003_inquiry_replied_at_inquiry_replied_by_inquiry_reply_and_more"),
    ]

    operations = [
        migrations.RunPython(raise_tickets, drop_tickets),
    ]
