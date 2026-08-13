"""Re-engagement for cancelled import orders.

The gap this closes: customers could always walk away, but nothing brought them
back. A cancelled order is the best lead the business has - the customer told
us exactly what they wanted and how far they were willing to go - so it is
worth a targeted message rather than a form letter.
"""

from django.conf import settings
from django.core.mail import send_mail


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
        from_email=None,
        recipient_list=["sales@goldridemotors.co.ke"],
        fail_silently=True,
    )


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
        from_email=None,
        recipient_list=[recipient],
        fail_silently=True,
    )
    return True
