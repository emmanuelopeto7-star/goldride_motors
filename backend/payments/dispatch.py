from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .mpesa import start_mpesa_payment
from .services import start_paystack_payment_detailed

MPESA_TRANSACTION_LIMIT = Decimal("250000")


def dispatch_payment(payment, email=None, phone=None):
    if payment.status != "pending":
        return False, "payment is not pending"

    if payment.method == "card":
        return _dispatch_card(payment, email)

    if payment.method == "mpesa":
        return _dispatch_mpesa(payment, phone)

    return False, "manual payments are recorded by staff"


def _dispatch_card(payment, email):
    if not email:
        return False, "an email address is required for a card payment"

    url, detail = start_paystack_payment_detailed(payment, email)
    if url is None:
        return False, detail

    payment.checkout_url = url
    payment.checkout_email = email
    # Stamped here rather than worked out on read, so the clock starts when
    # the link was actually minted - not when somebody happens to look.
    payment.checkout_expires_at = timezone.now() + timedelta(
        minutes=settings.CHECKOUT_LINK_MINUTES
    )
    payment.save(
        update_fields=[
            "checkout_url", "checkout_email", "checkout_expires_at", "updated_at"
        ]
    )
    return True, url


def _dispatch_mpesa(payment, phone):
    if not phone:
        return False, "a phone number is required for an M-PESA payment"

    if payment.amount > MPESA_TRANSACTION_LIMIT:
        return False, (
            f"amount exceeds the M-PESA limit of {MPESA_TRANSACTION_LIMIT:,.0f} KES - "
            "arrange a bank transfer"
        )

    result = start_mpesa_payment(payment, phone)
    if result is None or str(result.get("ResponseCode")) != "0":
        return False, "could not send the M-PESA prompt"

    return True, result.get("CheckoutRequestID")
