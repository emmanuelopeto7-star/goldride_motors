"""Telling the customer how to pay.

The gap this closes: approving a purchase produced a Paystack checkout URL,
stored it on the payment and returned it in the API response - to the member of
staff who clicked approve. Paystack's `initialize` call does not contact anyone
itself, so the link reached the customer only if they happened to sign in and
find the payment in their account. Approval is the moment they are waiting on,
so it is the moment that should reach them.

Every outcome is covered, not just the happy one. At this inventory's prices
the rails refuse more often than they accept - Paystack rejects large amounts
and M-PESA caps at 250,000 - and a customer whose purchase was approved but
whose payment fell back to manual is the one most in need of an email.
"""

import logging

from django.conf import settings

from goldride_app.mail import send as send_mail

from .pay_link import pay_link
from django.utils import timezone

logger = logging.getLogger("goldride.payments")


def _how_to_pay(payment):
    """The paragraph that differs per method. Returns None when there is
    nothing useful to say, so the caller can decline to send at all."""
    if payment.method == "card":
        # Our link, not the provider's. A Paystack checkout is a session that
        # is worth minutes; this one keeps working for as long as the invoice
        # is outstanding, and mints a fresh checkout whenever it is opened.
        return (
            f"Pay securely by card here:\n{pay_link(payment)}\n\n"
            "The link is personal to this order - please do not forward it."
        )

    if payment.method == "mpesa":
        return (
            "We have sent an M-PESA prompt to your phone. Enter your PIN to "
            "complete the payment. If it did not arrive, reply to this email "
            "and we will send it again."
        )

    if payment.method == "manual":
        reason = f" ({payment.note})" if payment.note else ""
        return (
            "This amount is above what our card and M-PESA rails accept"
            f"{reason}, so payment is by bank transfer. We will contact you "
            "with the account details."
        )

    return None


def _how_to_pay_now(payment):
    """The paragraph for an invoice that has only just been raised.

    Deliberately not `_how_to_pay`. That one is written for the moment after a
    checkout was minted or a prompt pushed and says so - "we have sent an
    M-PESA prompt to your phone" is false here, because nothing has been sent
    yet. The card line is the same either way: the pay link works from the
    moment the invoice exists, and mints its own checkout when opened.
    """
    if payment.method == "card":
        return (
            f"Pay securely by card here:\n{pay_link(payment)}\n\n"
            "The link is personal to this order - please do not forward it."
        )

    if payment.method == "mpesa":
        return (
            "You can start the M-PESA prompt yourself from your account:\n"
            f"{settings.FRONTEND_URL}/my/orders\n\n"
            "Or reply here and we will send one to your phone."
        )

    if payment.method == "manual":
        return (
            "This one is settled by bank transfer. We will follow up with the "
            "account details."
        )

    return None


def announce_payment_raised(payment):
    """Say in the chat that an invoice has been raised. Returns whether it went.

    The counterpart to `send_payment_instructions` for a payment raised by
    hand. Approval emails the customer because approval is the thing they were
    waiting on; a balance or a second instalment is not, and the thread about
    the car is where they are already talking to us about it. The alert is on -
    unlike the dispatch post, nothing else has just landed in their inbox, so
    a chat message nobody is told about would reach a customer who is not
    looking, which is to say nobody.

    Only orders that began as a purchase request have a thread. An order
    raised for a walk-in has none, and there is nowhere to post - the caller
    can see that from `checkout_sent_at` staying blank.

    Imported here rather than at the top: payments is imported by chat's own
    fixtures, and a module-level import the other way is a cycle.
    """
    from chat.system import post_to_ticket, ticket_for_payment

    instructions = _how_to_pay_now(payment)
    if instructions is None:
        return False

    try:
        message = post_to_ticket(
            ticket_for_payment(payment),
            (
                "A payment has been raised on your order.\n\n"
                f"Amount due: KES {payment.amount:,.0f}\n\n{instructions}"
            ),
        )
    except Exception:  # noqa: BLE001 - an invoice must survive a chat outage
        logger.exception("Could not announce payment %s", payment.pk)
        return False

    if message is None:
        return False

    # They have been told how to pay, which is what this field means - the
    # difference between waiting on them and waiting on us. The payments
    # screen reads it, so a staff-raised invoice stops looking unsent.
    payment.checkout_sent_at = timezone.now()
    payment.save(update_fields=["checkout_sent_at", "updated_at"])
    return True


def send_payment_instructions(payment, email):
    """Mail the customer whatever they need to do next. Returns whether it went.

    Stamps `checkout_sent_at` so staff can see it happened and are not left
    guessing whether to chase - the single most common question about a
    payment that has not moved.
    """
    if not email:
        return False

    instructions = _how_to_pay(payment)
    if instructions is None:
        return False

    order = payment.order
    send_mail(
        subject=f"Your purchase is approved - {order.car_title}",
        message=(
            f"Hello {order.customer_name},\n\n"
            f"Your purchase of {order.car_title} has been approved and the "
            f"car is reserved for you.\n\n"
            f"Amount due: KES {payment.amount:,.0f}\n\n"
            f"{instructions}\n\n"
            f"You can follow the order here:\n"
            f"{settings.FRONTEND_URL}/track/{order.token}\n\n"
            "Goldride Motors"
        ),
        to=[email],
    )

    payment.checkout_sent_at = timezone.now()
    payment.save(update_fields=["checkout_sent_at", "updated_at"])

    _post_to_the_conversation(payment, instructions)
    return True


def _post_to_the_conversation(payment, instructions):
    """Put the same instructions in the chat about this purchase.

    The email can be missed, filed by a spam rule, or sent to an address they
    never check; the thread is where they are already talking to us about
    this car. Same words in both places rather than a summary in one - a
    customer comparing them should not have to work out whether they differ.

    Imported here rather than at the top: payments is imported by chat's own
    fixtures, and a module-level import the other way is a cycle.
    """
    from chat.system import post_to_ticket, ticket_for_payment

    try:
        post_to_ticket(
            ticket_for_payment(payment),
            f"Amount due: KES {payment.amount:,.0f}\n\n{instructions}",
            # The email above just went. Alerting about the chat message would
            # be the same thing twice in one inbox.
            alert=False,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Could not post payment instructions for %s", payment.pk)
