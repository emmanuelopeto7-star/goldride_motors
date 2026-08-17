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

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


def _how_to_pay(payment):
    """The paragraph that differs per method. Returns None when there is
    nothing useful to say, so the caller can decline to send at all."""
    if payment.method == "card" and payment.checkout_url:
        return (
            f"Pay securely by card here:\n{payment.checkout_url}\n\n"
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
        from_email=None,
        recipient_list=[email],
        fail_silently=True,
    )

    payment.checkout_sent_at = timezone.now()
    payment.save(update_fields=["checkout_sent_at", "updated_at"])
    return True
