"""Who may read and write which conversation.

One place for the rule, because three call sites need it: the customer's REST
endpoints, the staff ones, and both socket consumers. A rule written out four
times is a rule that will disagree with itself.
"""

from tickets.models import Ticket

from .models import Conversation


def is_staff(user):
    return user.is_superuser or user.groups.filter(
        name__in=["Sales", "Manager"]
    ).exists()


def conversation_for(user, ticket_id, create=False):
    """The conversation on this ticket, if this user may have it.

    Returns None rather than raising, and returns None just the same whether
    the ticket does not exist or simply is not theirs - a customer probing ids
    must not be able to tell the difference.
    """
    ticket = (
        Ticket.objects.select_related(
            "purchase_request", "import_request", "inquiry"
        )
        .filter(pk=ticket_id)
        .first()
    )
    if ticket is None:
        return None

    if not is_staff(user):
        # A ticket raised by a guest has no customer, so nobody can claim it
        # by being signed in - `None == user` is never true here.
        if ticket.customer != user:
            return None

    if create:
        # Only ever created for a ticket that belongs to someone: there is
        # nowhere to deliver a reply for a guest's request.
        if ticket.customer is None:
            return None
        conversation, _ = Conversation.objects.get_or_create(ticket=ticket)
        return conversation

    return Conversation.objects.filter(ticket=ticket).first()
