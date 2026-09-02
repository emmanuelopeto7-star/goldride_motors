"""Answering an enquiry - once, by one person.

The whole reason this is a service and not three lines in a view: with several
agents watching the same queue, two of them replying to the same customer is
the failure everyone notices. The customer gets two different answers to one
question and has to work out which is real.
"""

from django.conf import settings
from django.utils import timezone

from goldride_app.mail import send as send_mail

from .models import Inquiry


def record_reply(inquiry, agent, message):
    """Answer an enquiry. Returns (claimed, emailed, detail).

    The claim on the reply is a conditional UPDATE, the same shape as claiming
    a ticket: `replied_at IS NULL` rides inside the write, so two agents
    clicking Send at the same moment cannot both pass. The guard comes first,
    before anything is sent, precisely because the email is the side effect
    that must not happen twice - an apology cannot unsend it.
    """
    taken = Inquiry.objects.filter(pk=inquiry.pk, replied_at__isnull=True).update(
        reply=message,
        replied_by=agent,
        replied_at=timezone.now(),
    )
    if not taken:
        return False, False, "this enquiry has already been answered"

    # A queryset .update() writes straight to the database and fires no
    # post_save, so the signal that settles a ticket never runs. Closing it
    # here keeps the queue honest; the signal still covers an edit made in
    # the admin.
    ticket = getattr(inquiry, "ticket", None)
    if ticket is not None:
        ticket.close()
        _add_to_conversation(ticket, agent, message)

    inquiry.refresh_from_db()

    if not inquiry.email:
        # Nothing to write to. The reply still stands as the record of what
        # was said on the phone, and the ticket still closes.
        return True, False, "no email address on this enquiry - recorded as a call"

    send_mail(
        subject=f"Re: your enquiry about {inquiry.car}",
        message=(
            f"{message}\n\n"
            f"- {agent.get_full_name() or agent.username}\n"
            f"{settings.SALES_EMAIL}"
        ),
        to=[inquiry.email],
    )
    Inquiry.objects.filter(pk=inquiry.pk).update(reply_emailed=True)
    inquiry.refresh_from_db()
    return True, True, "sent"


def _add_to_conversation(ticket, agent, message):
    """Put the reply in the chat as well as in the email.

    The same answer in both places on purpose: the customer gets it without
    signing in, and the thread reads as a conversation rather than starting
    mid-sentence next time either side opens it. Imported here rather than at
    the top because chat reaches back into inquiries - a module-level import
    either way round is a cycle.
    """
    from chat.models import Conversation
    from chat.services import send_message

    conversation, _ = Conversation.objects.get_or_create(ticket=ticket)
    send_message(conversation, sender=agent, body=message, from_staff=True)
