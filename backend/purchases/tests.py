"""Approval, end to end.

The step that had no tests despite doing the most: approving a purchase request
creates the import order, reserves the car, raises the payment, dispatches
collection and - as of now - tells the customer how to pay.

`dispatch_payment` is mocked at the module boundary. These are our decisions,
not Paystack's.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from cars.models import Car
from imports.models import ImportOrder
from payments.models import Payment
from tickets.models import Ticket

from .models import PurchaseRequest
from .services import approve_request, reject_request

DISPATCH = "purchases.services.dispatch_payment"


class ApprovalNotifiesTheCustomerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(
            "buyer", "buyer@example.com", "pw"
        )
        Group.objects.get_or_create(name="Customer")[0].user_set.add(self.customer)
        self.manager = User.objects.create_user("boss", "boss@goldride.co.ke", "pw")

        self.car = Car.objects.create(
            make="Toyota",
            model="Prado",
            year=2020,
            price=Decimal("8900000.00"),
            description="A car.",
        )
        self.request = PurchaseRequest.objects.create(
            customer=self.customer,
            car=self.car,
            preferred_method="card",
            phone="0712345678",
        )

    def approve(self):
        return approve_request(self.request, reviewed_by=self.manager)

    def test_a_dispatched_card_payment_emails_the_customer_the_link(self):
        """The whole point: the link used to stop at the API response."""
        def dispatched(payment, email=None, phone=None):
            payment.checkout_url = "https://checkout.paystack.com/xyz789"
            payment.save(update_fields=["checkout_url"])
            return True, payment.checkout_url

        mail.outbox.clear()
        with patch(DISPATCH, side_effect=dispatched):
            self.approve()

        to_customer = [m for m in mail.outbox if m.to == ["buyer@example.com"]]
        self.assertEqual(len(to_customer), 1)
        self.assertIn("https://checkout.paystack.com/xyz789", to_customer[0].body)

    def test_a_refused_payment_still_tells_the_customer_what_happens_next(self):
        """The common case at these prices, and the one that used to be silent."""
        mail.outbox.clear()
        with patch(DISPATCH, return_value=(False, "amount cannot be processed online")):
            self.approve()

        to_customer = [m for m in mail.outbox if m.to == ["buyer@example.com"]]
        self.assertEqual(len(to_customer), 1)
        self.assertIn("bank transfer", to_customer[0].body)
        self.assertIn("amount cannot be processed online", to_customer[0].body)

    def test_a_refused_payment_still_leaves_a_real_order(self):
        with patch(DISPATCH, return_value=(False, "too large")):
            payment, ok, _ = self.approve()

        self.assertFalse(ok)
        self.assertIsNotNone(payment)
        self.assertEqual(payment.method, "manual")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "approved")
        self.car.refresh_from_db()
        self.assertEqual(self.car.availability, "reserved")

    def test_sending_is_stamped_so_staff_can_see_it_went(self):
        with patch(DISPATCH, return_value=(False, "too large")):
            payment, _, _ = self.approve()

        payment.refresh_from_db()
        self.assertIsNotNone(payment.checkout_sent_at)

    def test_the_subject_names_the_car_readably(self):
        mail.outbox.clear()
        with patch(DISPATCH, return_value=(False, "too large")):
            self.approve()

        subject = [m for m in mail.outbox if m.to == ["buyer@example.com"]][0].subject
        self.assertIn("2020 Toyota Prado", subject)

    def test_the_stored_description_fits_its_column(self):
        """varchar(200), and Postgres raises DataError rather than truncating.
        The old Car.__str__ trailed the whole sales copy and overflowed it, so
        approving a car with a long description 500d in production."""
        self.car.description = "An extremely detailed writeup. " * 40
        self.car.save(update_fields=["description"])

        with patch(DISPATCH, return_value=(True, "ok")):
            self.approve()

        self.request.refresh_from_db()
        order = self.request.order
        self.assertLessEqual(len(order.car_description), 200)
        self.assertEqual(order.car_description, "2020 Toyota Prado")

    def test_the_order_str_stays_short(self):
        """It reaches customers through email subject lines."""
        with patch(DISPATCH, return_value=(True, "ok")):
            self.approve()

        self.request.refresh_from_db()
        self.assertLess(len(str(self.request.order)), 80)

    def test_approving_twice_is_refused(self):
        with patch(DISPATCH, return_value=(True, "ok")):
            self.approve()

        payment, ok, detail = self.approve()

        self.assertIsNone(payment)
        self.assertFalse(ok)
        self.assertEqual(Payment.objects.count(), 1)

    def test_a_customer_with_no_address_does_not_break_approval(self):
        """Nothing to send to, but the order and the reservation still stand."""
        self.customer.email = ""
        self.customer.save(update_fields=["email"])
        mail.outbox.clear()

        with patch(DISPATCH, return_value=(False, "too large")):
            payment, _, _ = self.approve()

        self.assertIsNotNone(payment)
        self.assertEqual([m for m in mail.outbox if m.to == [""]], [])
        payment.refresh_from_db()
        self.assertIsNone(payment.checkout_sent_at)


User = get_user_model()


class StaffPurchaseRequestDetailTests(APITestCase):
    """A ticket points at its subject by id, so the subject needs an address."""

    def setUp(self):
        self.car = Car.objects.create(
            make="Toyota", model="Prado", year=2019,
            price=Decimal("4250000.00"), description="A car.",
        )
        self.customer = User.objects.create_user("buyer", "buyer@x.com", "pw")
        self.request = PurchaseRequest.objects.create(
            customer=self.customer, car=self.car,
            preferred_method="card", phone="0712345678",
        )
        self.sales = User.objects.create_user("sales9", "sales9@x.com", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(self.sales)

    def test_sales_can_read_one_request(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.sales).key}"
        )

        response = self.client.get(f"/api/purchases/staff/{self.request.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.request.pk)
        self.assertEqual(response.data["car_title"], "2019 Toyota Prado")

    def test_a_customer_cannot(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.customer).key}"
        )

        response = self.client.get(f"/api/purchases/staff/{self.request.pk}/")

        self.assertEqual(response.status_code, 403)


class TwoManagersAtOnceTests(TestCase):
    """One request, two managers, the same moment.

    Each holds a copy of the row read before either clicked, so both copies
    say "pending" - which is precisely what a Python-side `if` believes. Only
    one may get through, or the customer is asked to pay twice for one car.
    """

    def setUp(self):
        self.car = Car.objects.create(
            make="Toyota", model="Prado", year=2019,
            price=Decimal("4250000.00"), description="A car.",
        )
        self.customer = User.objects.create_user("twice", "twice@x.com", "pw")
        self.asha = User.objects.create_user("m_asha", "asha@x.com", "pw")
        self.brian = User.objects.create_user("m_brian", "brian@x.com", "pw")
        self.request = PurchaseRequest.objects.create(
            customer=self.customer, car=self.car,
            preferred_method="card", phone="0712345678",
        )

    def stale_pair(self):
        """Two copies, both read while the request was still pending."""
        first = PurchaseRequest.objects.get(pk=self.request.pk)
        second = PurchaseRequest.objects.get(pk=self.request.pk)
        self.assertEqual(first.status, "pending")
        self.assertEqual(second.status, "pending")
        return first, second

    @patch(DISPATCH)
    def test_the_second_approval_is_refused(self, dispatch):
        dispatch.return_value = (True, "https://checkout.example/1")
        first, second = self.stale_pair()

        payment, _, _ = approve_request(first, reviewed_by=self.asha)
        refused, dispatched, detail = approve_request(second, reviewed_by=self.brian)

        self.assertIsNotNone(payment)
        self.assertIsNone(refused)
        self.assertFalse(dispatched)
        self.assertIn("already been reviewed", detail)

    @patch(DISPATCH)
    def test_the_customer_gets_one_order_one_payment_one_email(self, dispatch):
        # Writes the checkout URL onto the payment the way the real dispatch
        # does - without it there is nothing to put in the email and none is
        # sent, which would make this pass for the wrong reason.
        def dispatched(payment, email=None, phone=None):
            payment.checkout_url = "https://checkout.example/1"
            payment.save(update_fields=["checkout_url"])
            return True, payment.checkout_url

        dispatch.side_effect = dispatched
        first, second = self.stale_pair()
        mail.outbox = []

        approve_request(first, reviewed_by=self.asha)
        approve_request(second, reviewed_by=self.brian)

        self.assertEqual(ImportOrder.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    @patch(DISPATCH)
    def test_a_rejection_cannot_overwrite_an_approval(self, dispatch):
        """The decision note is the record of what the customer was told."""
        dispatch.return_value = (True, "https://checkout.example/1")
        first, second = self.stale_pair()

        approve_request(first, reviewed_by=self.asha, note="Cleared funds.")
        rejected, detail = reject_request(second, reviewed_by=self.brian, note="No.")

        self.assertFalse(rejected)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "approved")
        self.assertEqual(self.request.decision_note, "Cleared funds.")
        self.assertEqual(self.request.reviewed_by, self.asha)

    def test_the_second_rejection_is_refused(self):
        first, second = self.stale_pair()

        reject_request(first, reviewed_by=self.asha, note="Sold elsewhere.")
        rejected, detail = reject_request(second, reviewed_by=self.brian, note="No.")

        self.assertFalse(rejected)
        self.assertIn("already been reviewed", detail)
        self.request.refresh_from_db()
        self.assertEqual(self.request.decision_note, "Sold elsewhere.")

    @patch(DISPATCH)
    def test_only_one_ticket_close_happens(self, dispatch):
        """The ticket follows the decision, so it must not be settled twice."""
        dispatch.return_value = (True, "https://checkout.example/1")
        first, second = self.stale_pair()

        approve_request(first, reviewed_by=self.asha)
        approve_request(second, reviewed_by=self.brian)

        ticket = Ticket.objects.get(purchase_request=self.request)
        self.assertEqual(ticket.status, Ticket.CLOSED)
