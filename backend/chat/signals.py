"""An enquiry is already a message. It should read like one.

A customer types a question into the form on a car page; that is the first
thing said in the conversation about it. Leaving it out meant staff opened
the ticket, read the enquiry in one panel, and then answered in an empty chat
box underneath - two views of the same exchange, and the thread starting with
a reply to something invisible.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from inquiries.models import Inquiry

from .models import Conversation
from .services import send_message


@receiver(post_save, sender=Inquiry)
def seed_conversation(sender, instance, created, **kwargs):
    if not created or not instance.message:
        return

    # No account, no conversation: a chat message needs somewhere to land,
    # and a guest has contact details but nowhere to sign in.
    if instance.customer_id is None:
        return

    # The ticket is raised by the tickets app on this same signal. If it is
    # not there yet the conversation has nothing to hang off - better to skip
    # than to guess at an ordering between two apps' receivers.
    ticket = getattr(instance, "ticket", None)
    if ticket is None:
        return

    conversation, _ = Conversation.objects.get_or_create(ticket=ticket)
    send_message(
        conversation,
        sender=instance.customer,
        body=instance.message,
        from_staff=False,
    )
