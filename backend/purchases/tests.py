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

from cars.models import Car
from payments.models import Payment

from .models import PurchaseRequest
from .services import approve_request

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
