"""Following a pay link.

The link a customer is given points here, not at Paystack. Opening it mints a
fresh checkout and forwards them to it, so an email read tomorrow still works
while the session behind it is always minutes old.
"""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from imports.models import ImportOrder

from .models import Payment
from .pay_link import pay_link

User = get_user_model()
PAYSTACK = "payments.services.requests.post"


def a_payment(**overrides):
    customer = overrides.pop("customer", None)
    order = ImportOrder.objects.create(
        customer=customer,
        customer_name="Amina Otieno",
        phone="0712345678",
        car_description="Toyota Land Cruiser (2021)",
        total_amount=Decimal("5000.00"),
    )
    fields = {
        "order": order,
        "amount": Decimal("5000.00"),
        "method": "card",
        "status": "pending",
    }
    fields.update(overrides)
    return Payment.objects.create(**fields)


class PayLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.customer = User.objects.create_user(
            "amina", "amina@example.com", "pw"
        )

    def paystack(self, url="https://checkout.paystack.com/fresh"):
        patcher = patch(PAYSTACK)
        post = patcher.start()
        self.addCleanup(patcher.stop)
        post.return_value.json.return_value = {
            "status": True,
            "data": {"authorization_url": url},
        }
        return post

    def test_following_it_forwards_to_a_checkout(self):
        self.paystack()
        payment = a_payment(customer=self.customer)

        response = self.client.get(f"/pay/{payment.reference}/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://checkout.paystack.com/fresh")

    def test_it_mints_a_new_session_every_time(self):
        """The reason the link can outlive a checkout: each visit gets its own.
        Paystack refuses a reused reference, so this also has to be a fresh
        one each time."""
        post = self.paystack()
        payment = a_payment(customer=self.customer)

        self.client.get(f"/pay/{payment.reference}/")
        first = post.call_args.kwargs["json"]["reference"]
        self.client.get(f"/pay/{payment.reference}/")
        second = post.call_args.kwargs["json"]["reference"]

        self.assertNotEqual(first, second)

    def test_the_receipt_goes_to_the_account_on_the_order(self):
        """Not to anything in the request. Whoever opens the link cannot
        redirect where the receipt lands."""
        post = self.paystack()
        payment = a_payment(customer=self.customer)

        self.client.get(f"/pay/{payment.reference}/")

        self.assertEqual(post.call_args.kwargs["json"]["email"], "amina@example.com")

    def test_a_settled_invoice_goes_to_the_site_instead(self):
        self.paystack()
        payment = a_payment(customer=self.customer, status="paid")

        response = self.client.get(f"/pay/{payment.reference}/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("pay=unavailable", response.url)

    def test_an_unknown_reference_answers_the_same_way(self):
        """Settled, cancelled and never-existed are one answer: whoever holds
        this link is not owed a report on somebody's invoice."""
        response = self.client.get(f"/pay/{uuid.uuid4()}/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("pay=unavailable", response.url)

    def test_an_mpesa_invoice_is_not_a_card_checkout(self):
        payment = a_payment(customer=self.customer, method="mpesa")

        response = self.client.get(f"/pay/{payment.reference}/")

        self.assertIn("pay=unavailable", response.url)

    def test_a_refusal_from_paystack_lands_on_the_site(self):
        """Rather than a redirect to nowhere. At these prices Paystack
        refuses large amounts outright."""
        patcher = patch(PAYSTACK)
        post = patcher.start()
        self.addCleanup(patcher.stop)
        post.return_value.json.return_value = {
            "status": False,
            "message": "Amount cannot be processed online",
        }
        payment = a_payment(customer=self.customer)

        response = self.client.get(f"/pay/{payment.reference}/")

        self.assertIn("pay=unavailable", response.url)

    def test_the_link_is_built_from_the_reference(self):
        payment = a_payment(customer=self.customer)

        self.assertTrue(pay_link(payment).endswith(f"/pay/{payment.reference}/"))

    def test_the_serializer_offers_it_while_the_invoice_stands(self):
        from .serializers import PaymentSerializer

        payment = a_payment(customer=self.customer)

        data = PaymentSerializer(payment).data

        self.assertTrue(data["pay_url"].endswith(f"/pay/{payment.reference}/"))

    def test_the_serializer_stops_offering_it_once_paid(self):
        from .serializers import PaymentSerializer

        payment = a_payment(customer=self.customer, status="paid")

        self.assertIsNone(PaymentSerializer(payment).data["pay_url"])


class WalkInPayLinkTests(TestCase):
    """An order raised for somebody with no account.

    Staff can create one for a walk-in and dispatch a payment to an address
    they type in. That email carries a pay link, and the link has to work -
    it used to refuse forever, because it only ever looked for an account
    that was never there.
    """

    def setUp(self):
        cache.clear()
        patcher = patch(PAYSTACK)
        self.post = patcher.start()
        self.addCleanup(patcher.stop)
        self.post.return_value.json.return_value = {
            "status": True,
            "data": {"authorization_url": "https://checkout.paystack.com/walkin"},
        }
        # No customer: exactly the case that was broken.
        self.payment = a_payment()

    def test_dispatching_records_the_address_it_used(self):
        from .dispatch import dispatch_payment

        dispatch_payment(self.payment, email="walkin@example.com")

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.checkout_email, "walkin@example.com")

    def test_their_link_works(self):
        from .dispatch import dispatch_payment

        dispatch_payment(self.payment, email="walkin@example.com")

        response = self.client.get(f"/pay/{self.payment.reference}/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://checkout.paystack.com/walkin")

    def test_the_receipt_goes_where_it_went_before(self):
        from .dispatch import dispatch_payment

        dispatch_payment(self.payment, email="walkin@example.com")
        self.client.get(f"/pay/{self.payment.reference}/")

        self.assertEqual(
            self.post.call_args.kwargs["json"]["email"], "walkin@example.com"
        )

    def test_whoever_opens_it_cannot_choose_the_address(self):
        """The recorded one, never anything from the request."""
        from .dispatch import dispatch_payment

        dispatch_payment(self.payment, email="walkin@example.com")

        self.client.get(
            f"/pay/{self.payment.reference}/?email=attacker@example.com"
        )

        self.assertEqual(
            self.post.call_args.kwargs["json"]["email"], "walkin@example.com"
        )

    def test_an_account_still_wins_over_the_recorded_address(self):
        """If the order has an account, that is the address of record - a
        staff typo at dispatch time must not redirect their receipts."""
        from .dispatch import dispatch_payment

        customer = User.objects.create_user("owner", "owner@example.com", "pw")
        payment = a_payment(customer=customer)
        dispatch_payment(payment, email="typo@example.com")

        self.client.get(f"/pay/{payment.reference}/")

        self.assertEqual(
            self.post.call_args.kwargs["json"]["email"], "owner@example.com"
        )

    def test_a_payment_never_dispatched_still_declines(self):
        """Nothing recorded and no account: there is genuinely nowhere to
        send a receipt, so the link cannot mint anything."""
        response = self.client.get(f"/pay/{self.payment.reference}/")

        self.assertIn("pay=unavailable", response.url)
