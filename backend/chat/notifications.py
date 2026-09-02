"""Telling a customer, by email, that somebody replied.

Chat only works if it reaches people who are not looking at it. The whole
difficulty is doing that without becoming a nuisance: a quick back-and-forth
must not put five emails in an inbox, and somebody reading the thread as it
happens does not need to be told about it at all.

Two rules do the work:

  One alert per unread run. `customer_alerted_at` is compared with
  `customer_read_at`, not counted - once we have said "there is something
  waiting", saying it again adds nothing until they have looked.

  Nothing while they are plainly there. Reading the conversation within the
  last few minutes means the browser is open in front of them, and the
  websocket has already delivered the message.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from goldride_app.mail import send as send_mail

logger = logging.getLogger("goldride.chat")

# Long enough to cover a pause for thought mid-conversation, short enough that
# somebody who wandered off still hears about a reply.
STILL_WATCHING = timedelta(minutes=3)


def alert_customer(message):
    """Email the customer about a staff message, if they need telling."""
    conversation = message.conversation

    if not message.from_staff:
        return False

    customer = conversation.customer
    if customer is None or not customer.email:
        return False

    if _already_told_them(conversation):
        return False

    if _plainly_watching(conversation):
        return False

    ticket = conversation.ticket
    sent = send_mail(
        subject=f"Goldride replied about your {ticket.get_kind_display().lower()}",
        message=(
            f"{message.body}\n\n"
            f"Reply here:\n"
            f"{settings.FRONTEND_URL}/my/messages?about={ticket.pk}\n"
        ),
        to=[customer.email],
    )

    if sent:
        # Written through the queryset so this cannot trip the save() that
        # keeps last_message_at, and cannot race a read arriving meanwhile.
        type(conversation).objects.filter(pk=conversation.pk).update(
            customer_alerted_at=timezone.now()
        )
    return sent


def _already_told_them(conversation):
    alerted = conversation.customer_alerted_at
    if alerted is None:
        return False
    read = conversation.customer_read_at
    return read is None or alerted > read


def _plainly_watching(conversation):
    read = conversation.customer_read_at
    return read is not None and timezone.now() - read < STILL_WATCHING
