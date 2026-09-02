"""Saying something, from either side.

One path for both ends and both transports. The REST endpoints and - once
Channels lands - the socket consumer all come through here, so there is a
single place where a message is written, the other side's unread mark is
updated, and (next slice) the live broadcast happens. Two paths would drift
the first time one of them gained a rule the other did not.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Message

logger = logging.getLogger("goldride.chat")


def send_message(conversation, sender, body, from_staff, alert=True):
    """Say something. `alert` is off for messages that carry their own email.

    A payment link goes out as a proper email of its own and is posted into
    the thread as well; alerting on top would be the same thing twice in one
    inbox, moments apart.
    """
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        body=body,
        from_staff=from_staff,
    )

    # Sending is reading: you have obviously seen everything said before you
    # replied, so the sender's own side is caught up without a second call.
    conversation.mark_read(by_staff=from_staff)

    _broadcast(message)
    if alert:
        _alert(message)
    return message


def _broadcast(message):
    """Push it to whoever has the conversation open.

    Deliberately after the write and deliberately swallowing its own errors:
    the message is saved, and a live update that fails to fan out is a worse
    experience, not a lost one. Both sides poll on load, so the transcript is
    still correct - it just arrives on refresh rather than instantly. Letting
    a Redis hiccup turn into a 500 on a message already committed would be
    the wrong trade.
    """
    layer = get_channel_layer()
    if layer is None:
        return

    sender = message.sender
    payload = {
        "id": message.id,
        "body": message.body,
        "from_staff": message.from_staff,
        # The real name. The customer's consumer replaces it with "Goldride"
        # on the way out - shaping per audience there means one broadcast can
        # serve both sides.
        "sender_name": (
            (sender.get_full_name() or sender.username) if sender else "Goldride"
        ),
        "created_at": message.created_at.isoformat(),
    }

    try:
        async_to_sync(layer.group_send)(
            f"chat_{message.conversation_id}",
            {"type": "chat.message", "message": payload},
        )
    except Exception:  # noqa: BLE001 - see the docstring
        pass


def _alert(message):
    """Email the customer if they are not around to see it.

    Inline, and that is a compromise worth naming: it puts an SMTP round trip
    inside the request that sends a chat message, and chat is the one place
    where latency reads as broken. It is tolerable only because the rules in
    chat.notifications make it rare - at most one per unread run, and never
    while the customer is watching. The moment there is a background worker,
    this is the first thing that should move onto it.
    """
    from .notifications import alert_customer

    try:
        alert_customer(message)
    except Exception:  # noqa: BLE001
        # The mail wrapper does not raise, so this is belt and braces: a
        # message already saved and delivered must not fail on the way out.
        logger.exception("Could not alert about message %s", message.pk)
