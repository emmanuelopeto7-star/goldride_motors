from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from imports.models import ImportOrder
from payments.dispatch import dispatch_payment
from payments.models import Payment


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
        from_email=None,
        recipient_list=["sales@goldridemotors.co.ke"],
        fail_silently=True,
    )


@transaction.atomic
def approve_request(purchase_request, reviewed_by, note=""):
    if purchase_request.status != "pending":
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
        car_description=str(car),
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

    return payment, ok, detail


def reject_request(purchase_request, reviewed_by, note=""):
    if purchase_request.status != "pending":
        return False, "this request has already been reviewed"

    purchase_request.status = "rejected"
    purchase_request.decision_note = note
    purchase_request.reviewed_by = reviewed_by
    purchase_request.reviewed_at = timezone.now()
    purchase_request.save()

    return True, "rejected"
