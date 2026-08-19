"""Re-engagement for cancelled import orders.

The gap this closes: customers could always walk away, but nothing brought them
back. A cancelled order is the best lead the business has - the customer told
us exactly what they wanted and how far they were willing to go - so it is
worth a targeted message rather than a form letter.
"""

from django.conf import settings

from goldride_app.mail import send as send_mail


def notify_cancelled(order):
    """Tell sales an order was dropped, so someone can decide whether to chase."""
    send_mail(
        subject=f"Import order cancelled: {order.car_description}",
        message=(
            f"{order.customer_name} cancelled their order for "
            f"{order.car_description}.\n\n"
            f"Reason given: {order.cancel_reason or 'none given'}\n"
            f"Stage reached: {order.get_current_stage_display()}\n"
            f"Phone: {order.phone}\n\n"
            "Re-engage them at /api/staff/orders/ once there is something to "
            "offer."
        ),
        to=[settings.SALES_EMAIL],
    )


def notify_new_request(import_request):
    """Confirm to the customer, and put it in front of sales.

    Two messages because they are two jobs: the customer needs the link back
    to their request, and sourcing cannot start until somebody knows to look.
    """
    tracking = f"{settings.FRONTEND_URL}/imports/{import_request.token}"

    send_mail(
        subject=f"We are looking for your {import_request.make} {import_request.model}",
        message=(
            f"Hello {import_request.contact_name},\n\n"
            f"We have your request for a {import_request.year} "
            f"{import_request.make} {import_request.model} and have started "
            f"looking.\n\n"
            f"Follow it here - keep this link, it is how you get back to "
            f"it:\n{tracking}\n\n"
            "We will email you as soon as we have units to show you.\n\n"
            "Goldride Motors"
        ),
        to=[import_request.email],
    )

    send_mail(
        subject=f"Import request: {import_request.year} {import_request.make} "
                f"{import_request.model}",
        message=(
            f"{import_request.contact_name} ({import_request.phone}) is "
            f"looking for a {import_request.year} {import_request.make} "
            f"{import_request.model}.\n\n"
            f"Budget: {import_request.budget_kes or 'not stated'}\n"
            f"Notes: {import_request.notes or 'none'}\n\n"
            "Source units against it at /api/staff/import-requests/."
        ),
        to=[settings.SALES_EMAIL],
    )


def notify_units_sourced(import_request):
    """"We found some" - the email that brings them back to choose.

    Named in the client's documentation as the "Units Sourced" notification.
    It carries no prices: the point is to get them onto the selection page
    where the breakdown is laid out properly, not to negotiate in an inbox.
    """
    offered = import_request.units.filter(status="offered").count()
    if not offered:
        return False

    tracking = f"{settings.FRONTEND_URL}/imports/{import_request.token}"
    send_mail(
        subject=f"{offered} option{'s' if offered != 1 else ''} for your "
                f"{import_request.make} {import_request.model}",
        message=(
            f"Hello {import_request.contact_name},\n\n"
            f"We have found {offered} "
            f"{'units' if offered != 1 else 'unit'} matching your request. "
            f"Each one is listed with its full cost breakdown - what it lands "
            f"at, delivered and cleared.\n\n"
            f"Take a look and tell us which you want:\n{tracking}\n\n"
            "Goldride Motors"
        ),
        to=[import_request.email],
    )
    return True


def send_reengagement(order, message):
    """Mail the customer a reason to come back.

    The message is written by whoever is doing the chasing - a discount, a
    unit that has since been sourced - because a generic "we miss you" is
    worse than silence. Returns False when there is no address to send to.
    """
    recipient = order.customer.email if order.customer else ""
    if not recipient:
        return False

    tracking = f"{settings.FRONTEND_URL}/track/{order.token}"
    send_mail(
        subject=f"About your {order.car_description}",
        message=(
            f"Hello {order.customer_name},\n\n"
            f"{message}\n\n"
            f"Your order is open again and you can follow it here:\n{tracking}\n\n"
            "Goldride Motors"
        ),
        to=[recipient],
    )
    return True
