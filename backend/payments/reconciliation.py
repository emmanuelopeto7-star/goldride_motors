from datetime import timedelta

from django.utils import timezone

from .audit import settle
from .models import Payment, PaymentEvent
from .mpesa import query_mpesa_payment
from .services import verify_paystack_payment

MPESA_FAILURE_CODES = {"1", "1032", "1037", "2001"}
CARD_FAILURE_STATES = {"failed", "abandoned", "reversed"}

# Paystack reports an initialised-but-unpaid transaction as "abandoned"
# immediately, so a live checkout looks like a failure until the customer
# actually pays. Give them a window before believing it.
ABANDONED_GRACE = timedelta(minutes=30)


def reconcile_payment(payment):
    if payment.status != "pending":
        return False, "not pending"

    if payment.method == "card":
        return _reconcile_card(payment)
    if payment.method == "mpesa":
        return _reconcile_mpesa(payment)
    return False, "manual - staff decides"


def reconcile_pending(queryset=None):
    if queryset is None:
        queryset = Payment.objects.filter(status="pending")

    results = []
    for payment in queryset.order_by("created_at"):
        changed, message = reconcile_payment(payment)
        results.append((payment, changed, message))
    return results


def _reconcile_card(payment):
    if not payment.paystack_ref:
        return False, "never initiated"

    data = verify_paystack_payment(payment.paystack_ref)
    if data is None:
        return False, "no transaction at Paystack"

    state = data.get("status")

    if state == "success":
        if data.get("amount") != int(payment.amount * 100):
            return _mark(payment, "failed", note="amount mismatch")
        return _mark(payment, "paid", provider_ref=str(data.get("id")))

    if state in CARD_FAILURE_STATES:
        if (
            state == "abandoned"
            and timezone.now() - payment.created_at < ABANDONED_GRACE
        ):
            return False, "checkout still open"
        return _mark(payment, "failed", note=state)

    return False, f"still {state}"


def _reconcile_mpesa(payment):
    if not payment.checkout_request_id:
        return False, "never pushed"

    data = query_mpesa_payment(payment.checkout_request_id)
    if data is None:
        return False, "query failed"

    code = str(data.get("ResultCode"))
    desc = data.get("ResultDesc", "")

    if code == "0":
        return _mark(payment, "paid")

    if code in MPESA_FAILURE_CODES:
        return _mark(payment, "failed", note=desc[:200])

    return False, f"code {code} - still processing"


def _mark(payment, status, provider_ref=None, note=None):
    """The sweep's one way to write. See payments/audit.settle."""
    return settle(
        payment,
        to_status=status,
        source=PaymentEvent.RECONCILE,
        detail=note or f"provider reported {status}",
        provider_ref=provider_ref,
        note=note,
    )
