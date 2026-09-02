"""One way a payment's status changes, and one place it gets written down.

Before this, four pieces of code moved money between states - the Paystack
webhook, the M-PESA callback, reconciliation, and the record-by-hand view - and
each did its own locked update. They agreed, but only because somebody kept
them agreeing; and none of them left any trace of *why* a payment reads the way
it does. A payment marked `failed` could not tell you whether Paystack said so,
whether the sweep decided it, or whether a manager corrected it by hand.

`settle()` is now the only function that writes `Payment.status`. It does the
conditional update under a row lock exactly as before, and records a
`PaymentEvent` in the same transaction - so the history cannot drift from the
row it describes.
"""

import logging

from django.db import transaction

from .models import Payment, PaymentEvent

logger = logging.getLogger("goldride.payments")


def settle(
    payment,
    to_status,
    source,
    expected_status="pending",
    actor=None,
    detail="",
    provider_ref=None,
    note=None,
):
    """Move a payment to `to_status`, once, and record who moved it.

    `expected_status` is part of the UPDATE, not a Python `if`: two callers
    racing - a webhook arriving while the sweep is mid-flight - both read
    "pending", and a check-then-save would let both apply. Here the database
    decides, and the loser is told the row was already resolved.

    Pass `expected_status=None` for a correction, which is allowed to move a
    payment out of any state - that is what makes it a correction.

    Returns (changed, message).
    """
    with transaction.atomic():
        locked = Payment.objects.select_for_update().filter(pk=payment.pk)
        if expected_status is not None:
            locked = locked.filter(status=expected_status)
        locked = locked.first()

        if locked is None:
            return False, "already resolved"
        if locked.status == to_status:
            return False, f"already {to_status}"

        was = locked.status
        locked.status = to_status
        if provider_ref:
            locked.provider_ref = provider_ref
        if note is not None:
            locked.note = note[:200]
        # No update_fields: paid_at is stamped inside save(), and listing the
        # columns here would be one more place to forget it.
        locked.save()

        PaymentEvent.objects.create(
            payment=locked,
            from_status=was,
            to_status=to_status,
            source=source,
            detail=detail[:300],
            actor=actor,
        )

    payment.refresh_from_db()

    # Money changing state is worth a line in the log whatever else happens -
    # it is the first thing anybody looks for when a customer says they paid.
    logger.info(
        "payment %s %s -> %s (%s)%s",
        payment.reference,
        was,
        to_status,
        source,
        f" by {actor}" if actor else "",
    )
    return True, to_status
