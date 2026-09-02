"""Sending mail through Resend's HTTP API rather than SMTP.

Django's own SMTP backend would work - Resend speaks SMTP on smtp.resend.com -
but outbound SMTP is the thing managed hosts block, and finding that out after
everything else is wired up is a bad afternoon. This goes out over HTTPS, which
nothing blocks.

It is a backend rather than a change to `mail.py` so that nothing above it has
to know: `send_mail`, the nine call sites behind `goldride_app.mail.send`, and
`manage.py mailtest` all keep working, and switching back to SMTP or the
console is a change to one environment variable.
"""

import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger("goldride.mail")


class ResendBackend(BaseEmailBackend):
    """Django's email interface, delivered by Resend.

    `fail_silently` is honoured because Django's contract says so, but note
    that `goldride_app.mail.send` deliberately passes False and catches the
    exception itself - it wants the error so it can log which backend and
    which recipient it happened for.
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "RESEND_API_KEY", "")

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        if not self.api_key:
            # A missing key is configuration, not weather. Saying so once here
            # is better than nine identical failures further up.
            logger.error("RESEND_API_KEY is not set - no email can be sent")
            if not self.fail_silently:
                raise ValueError("RESEND_API_KEY is not set")
            return 0

        import resend

        resend.api_key = self.api_key

        sent = 0
        for message in email_messages:
            try:
                resend.Emails.send(self._payload(message))
            except Exception:
                logger.exception(
                    "Resend refused %r to %s",
                    message.subject,
                    ", ".join(message.recipients()),
                )
                if not self.fail_silently:
                    raise
                continue
            sent += 1
        return sent

    @staticmethod
    def _payload(message):
        """One EmailMessage as Resend wants it.

        Django hands us a plain-text body and, for EmailMultiAlternatives, an
        HTML alternative beside it. Resend needs at least one of `text`/`html`
        and is happy with both, so we send whatever the message actually has
        rather than inventing an HTML wrapper around plain text.
        """
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": message.subject,
            "text": message.body,
        }

        for content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html":
                payload["html"] = content
                break

        # Only sent when present: Resend rejects an empty list where it expects
        # addresses or nothing at all.
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        return payload
