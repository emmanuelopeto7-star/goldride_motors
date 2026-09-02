"""A checkout link lands in the conversation, not only in an inbox."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from rest_framework.test import APITestCase

from cars.models import Car
from imports.models import ImportOrder
from payments.models import Payment
from payments.notifications import send_payment_instructions
from purchases.models import PurchaseRequest
from purchases.services import approve_request

from .models import Conversation

User = get_user_model()
DISPATCH = "purchases.services.dispatch_payment"


def person(username, group):
    user = User.objects.create_user(username, f"{username}@example.com", "pw")
    Group.objects.get_or_create(name=group)[0].user_set.add(user)
    return user


class CheckoutLinkInTheChatTests(TestCase):
    def setUp(self):
        self.customer = person("wanjiru", "Customer")
        self.manager = person("mo", "Manager")
        self.car = Car.objects.create(
            make="Toyota", model="Prado", year=2019,
            price=Decimal("4250000.00"), description="A car.",
        )
        self.request = PurchaseRequest.objects.create(
            customer=self.customer, car=self.car,
            preferred_method="card", phone="0712345678",
        )
        mail.outbox = []

    def approve(self):
        """Approve with a dispatch that behaves like the real one."""
        def dispatched(payment, email=None, phone=None):
            payment.checkout_url = "https://checkout.paystack.com/abc123"
            payment.save(update_fields=["checkout_url"])
            return True, payment.checkout_url

        with patch(DISPATCH, side_effect=dispatched):
            return approve_request(self.request, reviewed_by=self.manager)

    def conversation(self):
        return Conversation.objects.get(ticket=self.request.ticket)

    def test_approving_puts_the_link_in_the_thread(self):
        self.approve()

        bodies = [m.body for m in self.conversation().messages.all()]

        self.assertEqual(len(bodies), 1)
        self.assertIn("/pay/", bodies[0])
        self.assertIn("4,250,000", bodies[0])

    def test_it_is_attributed_to_whoever_holds_the_ticket(self):
        """Their piece of work: when the customer comes back about the link,
        the thread says which colleague it went out under."""
        agent = person("asha", "Sales")
        self.request.ticket.claim(agent)

        self.approve()

        message = self.conversation().messages.first()
        self.assertTrue(message.from_staff)
        self.assertEqual(message.sender, agent)

    def test_an_unclaimed_ticket_speaks_for_the_dealership(self):
        """Nobody to attribute it to, and it is genuinely us speaking."""
        self.approve()

        self.assertIsNone(self.conversation().messages.first().sender)

    def test_the_customer_still_does_not_see_the_name(self):
        """Attribution is for us. Naming whoever is on shift invites the
        customer to ask for that person by name next time."""
        agent = person("asha", "Sales")
        self.request.ticket.claim(agent)
        self.approve()

        from .serializers import MessageSerializer

        message = self.conversation().messages.first()
        theirs = MessageSerializer(message, context={"for_staff": False}).data
        ours = MessageSerializer(message, context={"for_staff": True}).data

        self.assertEqual(theirs["sender_name"], "Goldride")
        self.assertEqual(ours["sender_name"], "asha")

    def test_the_email_still_goes(self):
        self.approve()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/pay/", mail.outbox[0].body)

    def test_the_customer_is_not_emailed_twice(self):
        """The instructions email has just gone. An alert about the chat
        message carrying the same link would be the same thing twice."""
        self.approve()

        self.assertEqual(len(mail.outbox), 1)

    def test_an_mpesa_purchase_says_what_to_expect(self):
        self.request.preferred_method = "mpesa"
        self.request.save(update_fields=["preferred_method"])

        with patch(DISPATCH, return_value=(True, "prompt sent")):
            approve_request(self.request, reviewed_by=self.manager)

        body = self.conversation().messages.first().body
        self.assertIn("M-PESA prompt", body)

    def test_an_order_with_no_ticket_behind_it_is_skipped(self):
        """Staff can raise an order for a walk-in. There is no purchase
        request, so no ticket and nowhere to post - the email still goes."""
        order = ImportOrder.objects.create(
            customer_name="Walk-in", phone="0712345678",
            car_description="2019 Toyota Prado",
            total_amount=Decimal("4250000.00"),
        )
        payment = Payment.objects.create(
            order=order, amount=Decimal("4250000.00"), method="card",
        )
        payment.checkout_url = "https://checkout.paystack.com/walkin"
        payment.save(update_fields=["checkout_url"])

        sent = send_payment_instructions(payment, "walkin@example.com")

        self.assertTrue(sent is not False)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_a_chat_failure_does_not_stop_the_email(self):
        """The email is the one that must not be lost - it reaches somebody
        who never signs in."""
        with patch(
            "chat.system.post_to_ticket", side_effect=RuntimeError("chat is down")
        ):
            self.approve()

        self.assertEqual(len(mail.outbox), 1)


class RaisedPaymentInTheChatTests(APITestCase):
    """An invoice raised by hand announces itself in the thread.

    Approval emails the customer because approval is what they were waiting
    on. A balance or a second instalment is not, and it used to reach nobody
    at all until somebody remembered to dispatch it - so raising one now posts
    into the conversation about that car, with an alert, and says how to pay.
    """

    URL = "/api/staff/payments/"

    def setUp(self):
        self.customer = person("wanjiru", "Customer")
        self.manager = person("mo", "Manager")
        car = Car.objects.create(
            make="Toyota", model="Prado", year=2019,
            price=Decimal("4250000.00"), description="A car.",
        )
        self.request = PurchaseRequest.objects.create(
            customer=self.customer, car=car,
            preferred_method="card", phone="0712345678",
        )

        # Approving is what gives the order a ticket and a conversation, which
        # is the situation a second invoice is raised into.
        with patch(DISPATCH, return_value=(True, "https://checkout/abc")):
            approve_request(self.request, reviewed_by=self.manager)

        self.request.refresh_from_db()
        self.order = self.request.order
        self.client.force_authenticate(user=self.manager)
        mail.outbox = []

    def conversation(self):
        return Conversation.objects.get(ticket=self.request.ticket)

    def raise_payment(self, **overrides):
        body = {"order": self.order.id, "amount": "500000.00", "method": "card"}
        body.update(overrides)
        return self.client.post(self.URL, body, format="json")

    def test_raising_one_posts_it_to_the_thread(self):
        before = self.conversation().messages.count()

        response = self.raise_payment()

        self.assertEqual(response.status_code, 201)
        messages = self.conversation().messages.all()
        self.assertEqual(messages.count(), before + 1)
        self.assertIn("500,000", messages.last().body)

    def test_the_message_carries_a_link_they_can_pay_with(self):
        self.raise_payment()

        self.assertIn("/pay/", self.conversation().messages.last().body)

    def test_the_customer_is_alerted(self):
        """Nothing else lands in their inbox when an invoice is raised, so a
        message nobody is told about reaches a customer who is not looking."""
        self.raise_payment()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/my/messages", mail.outbox[0].body)

    def test_an_mpesa_invoice_does_not_claim_a_prompt_was_sent(self):
        """Raising is not dispatching. Nothing has reached their phone yet."""
        self.raise_payment(method="mpesa", amount="200000.00")

        body = self.conversation().messages.last().body
        self.assertNotIn("We have sent", body)
        self.assertIn("/my/orders", body)

    def test_a_bank_transfer_says_details_are_coming(self):
        body_before = self.raise_payment(method="manual")

        self.assertEqual(body_before.status_code, 201)
        self.assertIn("bank transfer", self.conversation().messages.last().body)

    def test_the_payment_no_longer_reads_as_unsent(self):
        """checkout_sent_at is what the dashboard reads to decide whether it is
        waiting on them or on us. They have been told, so it is on them."""
        response = self.raise_payment()

        self.assertIsNotNone(response.data["checkout_sent_at"])
        self.assertIsNotNone(
            Payment.objects.get(reference=response.data["reference"]).checkout_sent_at
        )

    def test_a_walk_in_order_has_nowhere_to_post(self):
        """No purchase request behind it means no ticket and no thread. The
        invoice still stands, and staff can see nobody was told."""
        walk_in = ImportOrder.objects.create(
            customer_name="Walk-in", phone="0712345678",
            car_description="2019 Toyota Prado",
            total_amount=Decimal("900000.00"),
        )

        response = self.raise_payment(order=walk_in.id)

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["checkout_sent_at"])
        self.assertEqual(self.conversation().messages.count(), 1)

    def test_a_chat_outage_does_not_lose_the_invoice(self):
        """The money record is the thing that must survive. A thread that
        missed a message is a nuisance; a payment that was never raised is a
        car nobody asked to be paid for."""
        with patch(
            "chat.system.post_to_ticket", side_effect=RuntimeError("chat is down")
        ):
            response = self.raise_payment()

        self.assertEqual(response.status_code, 201)
        payment = Payment.objects.get(reference=response.data["reference"])
        self.assertIsNone(payment.checkout_sent_at)
