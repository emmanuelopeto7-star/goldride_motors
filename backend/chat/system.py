"""Messages the system puts in a conversation on somebody's behalf.

Attributed to whoever holds the ticket. It is their piece of work, and when a
customer comes back three days later asking about the link, the thread should
say which colleague it went out under rather than leaving the team to guess.

This changes nothing for the customer: staff names are never shown to them,
so it still reads as "Goldride" on their side. The attribution is for us.

An unclaimed ticket has nobody to attribute to, and then it is genuinely the
dealership speaking - sender stays null and both sides read "Goldride".
"""

import logging

from .models import Conversation
from .services import send_message

logger = logging.getLogger("goldride.chat")


def post_to_ticket(ticket, body, alert=True):
    """Put a message in this ticket's conversation, if it can have one."""
    if ticket is None or ticket.customer is None:
        return None

    conversation, _ = Conversation.objects.get_or_create(ticket=ticket)
    return send_message(
        conversation,
        sender=ticket.claimed_by,
        body=body,
        from_staff=True,
        alert=alert,
    )


def ticket_for_payment(payment):
    """The ticket a payment came from, if it came from one.

    Payments hang off orders, and an order usually starts life as a purchase
    request - but not always: staff can raise one directly for a walk-in, and
    that has no ticket and no conversation.
    """
    order = payment.order
    if order is None:
        return None

    request = getattr(order, "purchase_request", None)
    if request is None:
        return None

    return getattr(request, "ticket", None)
