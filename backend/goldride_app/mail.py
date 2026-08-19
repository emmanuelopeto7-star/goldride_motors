"""One way out for every email this system sends.

Every call site used `send_mail(..., fail_silently=True)`, which is right in
spirit - a customer's order must not fail because a mail server is down - but
wrong in practice: it swallows the exception and tells nobody. A misconfigured
SMTP host looked exactly like a working one, which is how the whole system ran
on the console backend without anybody noticing that no email had ever left it.

This keeps the never-raise behaviour and adds the missing half: the failure is
logged with enough detail to act on, and the caller learns whether it worked.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail as django_send_mail

logger = logging.getLogger("goldride.mail")


def send(subject, message, to, from_email=None):
    """Send one email. Returns True if it went, False if it did not.

    Never raises. Callers are in the middle of approving a sale or cancelling
    an order, and neither should fail because a mail server did.
    """
    recipients = [address for address in (to if isinstance(to, list) else [to]) if address]
    if not recipients:
        logger.warning("Not sending %r - no recipient address", subject)
        return False

    try:
        sent = django_send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipients,
            # False on purpose: we want the exception so it can be logged.
            # The try/except below is what keeps the promise not to raise.
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Email failed: %r to %s via %s",
            subject,
            ", ".join(recipients),
            settings.EMAIL_BACKEND,
        )
        return False

    if not sent:
        logger.error("Email reported 0 sent: %r to %s", subject, ", ".join(recipients))
        return False

    logger.info("Email sent: %r to %s", subject, ", ".join(recipients))
    return True
