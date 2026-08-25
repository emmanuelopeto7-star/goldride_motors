from django.conf import settings
from django.db import transaction
from django.utils import timezone

from imports.models import ImportOrder
from payments.dispatch import dispatch_payment
from payments.models import Payment
from payments.notifications import send_payment_instructions

from goldride_app.mail import send as send_mail

from .models import PurchaseRequest


def notify_sales(purchase_request):
    send_mail(
        subject=f"Purchase request: {purchase_request.car}",
        message=(
            f"{purchase_request.customer} wants to buy {purchase_request.car} "
            f"outright for {purchase_request.car.price} KES.\n\n"
            f"Preferred method: {purchase_request.get_preferred_method_display()}\n"
            f"Phone: {purchase_request.phone}\n\n"
            f"{purchase_request.message}\n\n"
            "Approve or reject it at /api/purchases/staff/."
        ),
        to=[settings.SALES_EMAIL],
    )


@transaction.atomic
def approve_request(purchase_request, reviewed_by, note=""):
    # Re-read the status from the database under a row lock rather than
    # trusting the copy handed in. The caller fetched that copy before this
    # transaction opened, so two managers clicking Approve at the same moment
    # both hold an object saying "pending" - and a plain `if` believes both.
    # Each would create an order, a payment and a checkout link, and the
    # customer would be asked to pay twice for one car.
    #
    # The lock is held until this transaction commits, which includes the call
    # out to Paystack or Daraja. That is deliberate: it only serialises two
    # attempts on the *same* request, which is exactly the pair that must not
    # both proceed.
    locked_status = (
        PurchaseRequest.objects.select_for_update()
        .filter(pk=purchase_request.pk)
        .values_list("status", flat=True)
        .first()
    )
    if locked_status != "pending":
        return None, False, "this request has already been reviewed"

    car = purchase_request.car
    if car.availability == "sold":
        return None, False, "this car has already been sold"

    order = ImportOrder.objects.create(
        customer=purchase_request.customer,
        customer_name=purchase_request.customer.get_full_name()
        or purchase_request.customer.username,
        phone=purchase_request.phone,
        car=car,
        # Sliced to the column width. str(car) is short now, but this field is
        # varchar(200) and Postgres raises DataError rather than truncating -
        # the last thing that should 500 is approving a sale.
        car_description=str(car)[:200],
        total_amount=car.price,
    )

    payment = Payment.objects.create(
        order=order,
        amount=car.price,
        method=purchase_request.preferred_method,
    )

    purchase_request.status = "approved"
    purchase_request.decision_note = note
    purchase_request.reviewed_by = reviewed_by
    purchase_request.reviewed_at = timezone.now()
    purchase_request.order = order
    purchase_request.save()

    ok, detail = dispatch_payment(
        payment,
        email=purchase_request.customer.email,
        phone=purchase_request.phone,
    )

    if not ok:
        # The invoice stands either way - it just has to be collected by hand.
        payment.method = "manual"
        payment.note = f"online payment unavailable: {detail}"[:200]
        payment.save(update_fields=["method", "note", "updated_at"])

    # After the branch above, so the mail describes what actually happened
    # rather than what we hoped would. Sent on failure too: an approval the
    # customer never hears about is the worst of the three outcomes.
    send_payment_instructions(payment, purchase_request.customer.email)

    return payment, ok, detail


@transaction.atomic
def reject_request(purchase_request, reviewed_by, note=""):
    # Same race as approving, and the same fix. Rejecting twice writes a
    # second decision note over the first, so the record of who turned the
    # customer down - and why - is the loser's, not the winner's.
    locked_status = (
        PurchaseRequest.objects.select_for_update()
        .filter(pk=purchase_request.pk)
        .values_list("status", flat=True)
        .first()
    )
    if locked_status != "pending":
        return False, "this request has already been reviewed"

    purchase_request.status = "rejected"
    purchase_request.decision_note = note
    purchase_request.reviewed_by = reviewed_by
    purchase_request.reviewed_at = timezone.now()
    purchase_request.save()

    return True, "rejected"
