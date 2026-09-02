"""The Resend backend, without touching Resend.

Every test here fakes `resend.Emails.send` and inspects the payload it was
handed. That is the whole surface worth testing: the mapping from Django's
EmailMessage onto Resend's shape, and what happens when it refuses.
"""

from unittest.mock import patch

from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from django.test import TestCase, override_settings

from goldride_app.mail import send

BACKEND = "goldride_app.email_backends.ResendBackend"


@override_settings(EMAIL_BACKEND=BACKEND, RESEND_API_KEY="re_test", DEFAULT_FROM_EMAIL="noreply@goldride.test")
class ResendBackendTests(TestCase):
    def payload_from(self, message):
        """Send one message and return what Resend would have received."""
        with patch("resend.Emails.send") as resend_send:
            message.send()
        self.assertTrue(resend_send.called, "nothing was sent to Resend")
        return resend_send.call_args[0][0]

    def test_sends_the_plain_body_as_text(self):
        payload = self.payload_from(
            EmailMessage("Your deposit", "We have it.", to=["buyer@example.com"])
        )

        self.assertEqual(payload["subject"], "Your deposit")
        self.assertEqual(payload["text"], "We have it.")
        self.assertEqual(payload["to"], ["buyer@example.com"])

    def test_falls_back_to_the_default_sender(self):
        payload = self.payload_from(
            EmailMessage("Subject", "Body", to=["buyer@example.com"])
        )

        self.assertEqual(payload["from"], "noreply@goldride.test")

    def test_carries_an_html_alternative_when_there_is_one(self):
        message = EmailMultiAlternatives("Subject", "plain", to=["buyer@example.com"])
        message.attach_alternative("<p>rich</p>", "text/html")

        payload = self.payload_from(message)

        self.assertEqual(payload["text"], "plain")
        self.assertEqual(payload["html"], "<p>rich</p>")

    def test_invents_no_html_for_a_plain_message(self):
        # Resend accepts text alone. Wrapping it in markup would change what
        # the recipient sees for no reason anybody asked for.
        payload = self.payload_from(
            EmailMessage("Subject", "plain only", to=["buyer@example.com"])
        )

        self.assertNotIn("html", payload)

    def test_omits_empty_address_lists(self):
        # Resend rejects an empty list where it expects addresses or nothing.
        payload = self.payload_from(
            EmailMessage("Subject", "Body", to=["buyer@example.com"])
        )

        for field in ("cc", "bcc", "reply_to"):
            self.assertNotIn(field, payload)

    def test_passes_cc_bcc_and_reply_to_when_present(self):
        payload = self.payload_from(
            EmailMessage(
                "Subject",
                "Body",
                to=["buyer@example.com"],
                cc=["sales@goldride.test"],
                bcc=["audit@goldride.test"],
                reply_to=["desk@goldride.test"],
            )
        )

        self.assertEqual(payload["cc"], ["sales@goldride.test"])
        self.assertEqual(payload["bcc"], ["audit@goldride.test"])
        self.assertEqual(payload["reply_to"], ["desk@goldride.test"])

    def test_counts_what_it_sent(self):
        with patch("resend.Emails.send"):
            sent = send_mail("Subject", "Body", None, ["buyer@example.com"])

        self.assertEqual(sent, 1)

    def test_a_refusal_reaches_the_caller_rather_than_being_swallowed(self):
        with patch("resend.Emails.send", side_effect=RuntimeError("domain not verified")):
            with self.assertRaises(RuntimeError):
                send_mail("Subject", "Body", None, ["buyer@example.com"], fail_silently=False)

    def test_mail_send_reports_failure_without_raising(self):
        # The nine call sites are mid-sale. They must learn it failed and carry
        # on, which is the whole point of goldride_app.mail.
        with patch("resend.Emails.send", side_effect=RuntimeError("domain not verified")):
            self.assertIs(send("Subject", "Body", "buyer@example.com"), False)


@override_settings(EMAIL_BACKEND=BACKEND, RESEND_API_KEY="")
class MissingKeyTests(TestCase):
    def test_says_the_key_is_missing_instead_of_calling_resend(self):
        with patch("resend.Emails.send") as resend_send:
            with self.assertRaises(ValueError):
                send_mail("Subject", "Body", None, ["buyer@example.com"])

        self.assertFalse(resend_send.called)

    def test_an_unconfigured_key_does_not_take_a_sale_down(self):
        with patch("resend.Emails.send"):
            self.assertIs(send("Subject", "Body", "buyer@example.com"), False)
