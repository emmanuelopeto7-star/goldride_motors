"""A dealer application raises a ticket, and its decision closes it.

A signal rather than a line in the view, for the reason the other three kinds
use one: an application can arrive from the API, the admin, a management
command or a test, and a queue that only knows about one of those paths is a
queue that silently loses work.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import Ticket

from .models import DealerApplication

SETTLED = {DealerApplication.APPROVED, DealerApplication.REJECTED}


@receiver(post_save, sender=DealerApplication)
def dealer_application_ticket(sender, instance, created, **kwargs):
    if created:
        Ticket.objects.get_or_create(
            dealer_application=instance, defaults={"kind": Ticket.DEALER}
        )
        return

    if instance.status in SETTLED:
        ticket = (
            Ticket.objects.filter(dealer_application=instance)
            .exclude(status=Ticket.CLOSED)
            .first()
        )
        if ticket is not None:
            ticket.close()
