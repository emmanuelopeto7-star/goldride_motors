"""Emailing a customer about a reply - without becoming a nuisance."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from cars.models import Car
from inquiries.models import Inquiry

from .models import Conversation
from .services import send_message

User = get_user_model()


def person(username, group, email=None):
    user = User.objects.create_user(
        username, email if email is not None else f"{username}@example.com", "pw"
    )
    Group.objects.get_or_create(name=group)[0].user_set.add(user)
    return user


def ticket_for(customer):
    car = Car.objects.create(
        make="Toyota", model="Prado", year=2019,
        price=Decimal("4250000.00"), description="A car.",
    )
    return Inquiry.objects.create(
        car=car, customer=customer, name=customer.username,
        phone="0712345678", email=customer.email, message="",
    ).ticket


class AlertTests(TestCase):
    def setUp(self):
        self.customer = person("wanjiru", "Customer")
        self.agent = person("asha", "Sales")
        self.conversation = Conversation.objects.create(
            ticket=ticket_for(self.customer)
        )
        mail.outbox = []

    def reply(self, body="Yes, it is."):
        return send_message(self.conversation, self.agent, body, from_staff=True)

    def test_a_reply_emails_the_customer(self):
        self.reply()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["wanjiru@example.com"])
        self.assertIn("Yes, it is.", mail.outbox[0].body)

    def test_the_email_links_to_the_conversation(self):
        self.reply()

        self.assertIn(
            f"/my/messages?about={self.conversation.ticket.pk}", mail.outbox[0].body
        )

    def test_a_customers_own_message_emails_nobody(self):
        send_message(self.conversation, self.customer, "Hello?", from_staff=False)

        self.assertEqual(len(mail.outbox), 0)

    def test_a_burst_of_replies_is_one_email(self):
        """The rule that keeps this bearable: once they have been told there
        is something waiting, saying it again adds nothing."""
        self.reply("One.")
        self.reply("Two.")
        self.reply("Three.")

        self.assertEqual(len(mail.outbox), 1)

    def test_reading_it_arms_the_next_alert(self):
        """Alerted an hour ago, read half an hour ago, replied to now: they
        have looked since we last told them, and are no longer watching, so
        the next reply is worth an email."""
        self.reply("One.")
        self.assertEqual(len(mail.outbox), 1)

        now = timezone.now()
        Conversation.objects.filter(pk=self.conversation.pk).update(
            customer_alerted_at=now - timedelta(hours=1),
            customer_read_at=now - timedelta(minutes=30),
        )
        self.conversation.refresh_from_db()

        self.reply("Two.")

        self.assertEqual(len(mail.outbox), 2)

    def test_nothing_is_sent_while_they_are_plainly_watching(self):
        """Read a moment ago means the page is open and the websocket has
        already put the message in front of them."""
        self.conversation.mark_read(by_staff=False)

        self.reply()

        self.assertEqual(len(mail.outbox), 0)

    def test_an_account_with_no_address_is_skipped(self):
        silent = person("noaddress", "Customer", email="")
        conversation = Conversation.objects.create(ticket=ticket_for(silent))

        send_message(conversation, self.agent, "Hello?", from_staff=True)

        self.assertEqual(len(mail.outbox), 0)

    def test_a_failed_send_does_not_lose_the_message(self):
        """The message is already saved and already on the socket. A mail
        server having a bad day must not turn that into an error."""
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            EMAIL_HOST="127.0.0.1",
            EMAIL_PORT=1,
        ):
            message = self.reply("Sent anyway.")

        self.assertIsNotNone(message.pk)
        self.assertEqual(self.conversation.messages.count(), 1)

    def test_a_failed_send_is_tried_again_next_time(self):
        """customer_alerted_at only moves when an email actually went, so a
        failure does not silence the next reply."""
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            EMAIL_HOST="127.0.0.1",
            EMAIL_PORT=1,
        ):
            self.reply("First.")

        self.conversation.refresh_from_db()
        self.assertIsNone(self.conversation.customer_alerted_at)

        self.reply("Second.")

        self.assertEqual(len(mail.outbox), 1)
