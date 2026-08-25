from django.db.models.signals import post_save
from django.dispatch import receiver

from imports.models import ImportRequest
from inquiries.models import Inquiry
from purchases.models import PurchaseRequest

from .models import Ticket

# The statuses that mean somebody has already decided. A ticket that outlives
# its decision is worse than no ticket: the queue fills with settled work and
# staff stop trusting it.
PURCHASE_SETTLED = {"approved", "rejected"}
IMPORT_SETTLED = {"agreed", "cancelled"}


def _settle(**subject):
    """Close whatever ticket is still live for this request, if any."""
    ticket = Ticket.objects.filter(**subject).exclude(status=Ticket.CLOSED).first()
    if ticket is not None:
        ticket.close()


@receiver(post_save, sender=PurchaseRequest)
def purchase_request_ticket(sender, instance, created, **kwargs):
    """Raise the ticket on arrival, close it on the decision.

    A signal rather than a line in the view because a purchase request can be
    created from the API, the admin, a management command or a test, and a
    queue that only knows about one of those paths is a queue that silently
    loses work.
    """
    if created:
        Ticket.objects.get_or_create(
            purchase_request=instance, defaults={"kind": Ticket.APPROVAL}
        )
    elif instance.status in PURCHASE_SETTLED:
        _settle(purchase_request=instance)


@receiver(post_save, sender=ImportRequest)
def import_request_ticket(sender, instance, created, **kwargs):
    if created:
        Ticket.objects.get_or_create(
            import_request=instance, defaults={"kind": Ticket.SOURCING}
        )
    elif instance.status in IMPORT_SETTLED:
        _settle(import_request=instance)


@receiver(post_save, sender=Inquiry)
def inquiry_ticket(sender, instance, created, **kwargs):
    """An enquiry has no status column - the reply is its status.

    This is the kind the queue existed for: several agents watching the same
    list, and a customer who must get one answer rather than three.
    """
    if created:
        Ticket.objects.get_or_create(
            inquiry=instance, defaults={"kind": Ticket.ENQUIRY}
        )
    elif instance.replied_at is not None:
        _settle(inquiry=instance)
