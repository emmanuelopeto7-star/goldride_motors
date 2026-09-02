"""The link a customer is actually given.

A Paystack checkout URL is a session, not an address: it is minted by their
initialize call and worth showing for minutes, which is a poor thing to put in
an email somebody opens tomorrow. So what goes out is a link to us, keyed on
the payment reference, and clicking it mints a fresh checkout and forwards
them to it.

The reference is the credential, exactly as the UUID in a tracking link is.
That is a deliberate trade: the alternative is making somebody sign in to pay
an invoice they were emailed, which is how invoices go unpaid. What it buys an
attacker who guesses one is the ability to pay somebody else's bill - the
receipt still goes to the account's own address, because the email comes off
the order rather than off the request.
"""

from django.conf import settings


def pay_link(payment):
    """Where to send somebody to pay this."""
    return f"{settings.SITE_URL}/pay/{payment.reference}/"
