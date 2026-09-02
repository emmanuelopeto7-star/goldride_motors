"""A checkout link is only offered for a few minutes.

Ours, not Paystack's: their initialize call takes no expiry, so the URL keeps
working at their end. What these pin down is that the app stops handing it out
and offers a fresh one instead.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from imports.models import ImportOrder

from .dispatch import dispatch_payment
from .models import Payment
from .notifications import send_payment_instructions
from .serializers import PaymentSerializer

User = get_user_model()
PAYSTACK = "payments.services.requests.post"


def an_order(customer=None):
    return ImportOrder.objects.create(
        customer=customer,
        customer_name="Amina Otieno",
        phone="0712345678",
        car_description="Toyota Land Cruiser (2021)",
        total_amount=Decimal("5000.00"),
    )


def a_payment(**overrides):
    fields = {
        "order": overrides.pop("order", None) or an_order(),
        "amount": Decimal("5000.00"),
        "method": "card",
        "status": "pending",
    }
    fields.update(overrides)
    return Payment.objects.create(**fields)


def paystack_returns_a_url():
    patcher = patch(PAYSTACK)
    post = patcher.start()
    post.return_value.json.return_value = {
        "status": True,
        "data": {"authorization_url": "https://checkout.paystack.com/abc123"},
    }
    return patcher


class ExpiryIsStampedTests(TestCase):
    def setUp(self):
        self.patcher = paystack_returns_a_url()
        self.addCleanup(self.patcher.stop)

    def test_dispatching_starts_the_clock(self):
        payment = a_payment()

        dispatch_payment(payment, email="amina@example.com")

        payment.refresh_from_db()
        self.assertIsNotNone(payment.checkout_expires_at)
        self.assertTrue(payment.checkout_is_live)

    @override_settings(CHECKOUT_LINK_MINUTES=10)
    def test_it_lasts_the_configured_number_of_minutes(self):
        payment = a_payment()
        before = timezone.now()

        dispatch_payment(payment, email="amina@example.com")

        payment.refresh_from_db()
        lasted = payment.checkout_expires_at - before
        self.assertGreater(lasted, timedelta(minutes=9))
        self.assertLess(lasted, timedelta(minutes=11))

    def test_the_clock_starts_when_the_link_was_minted(self):
        """Not when somebody happens to look at it - otherwise an invoice
        nobody opened would stay live indefinitely."""
        payment = a_payment()
        dispatch_payment(payment, email="amina@example.com")
        payment.refresh_from_db()

        first = payment.checkout_expires_at
        payment.refresh_from_db()

        self.assertEqual(first, payment.checkout_expires_at)

    def test_a_stale_link_is_no_longer_live(self):
        payment = a_payment()
        dispatch_payment(payment, email="amina@example.com")
        Payment.objects.filter(pk=payment.pk).update(
            checkout_expires_at=timezone.now() - timedelta(seconds=1)
        )
        payment.refresh_from_db()

        self.assertFalse(payment.checkout_is_live)

    def test_asking_again_gets_a_fresh_one(self):
        """The recovery path. An expired link is not a dead end."""
        payment = a_payment()
        dispatch_payment(payment, email="amina@example.com")
        Payment.objects.filter(pk=payment.pk).update(
            checkout_expires_at=timezone.now() - timedelta(minutes=5)
        )
        payment.refresh_from_db()
        self.assertFalse(payment.checkout_is_live)

        dispatch_payment(payment, email="amina@example.com")

        payment.refresh_from_db()
        self.assertTrue(payment.checkout_is_live)

    def test_an_invoice_raised_before_links_expired_still_counts_as_live(self):
        """No expiry stamped means it predates the rule. Retiring every old
        invoice on deploy would be a worse answer than leaving them alone."""
        payment = a_payment(checkout_url="https://checkout.paystack.com/old")

        self.assertIsNone(payment.checkout_expires_at)
        self.assertTrue(payment.checkout_is_live)

    def test_a_payment_with_no_link_is_not_live(self):
        self.assertFalse(a_payment().checkout_is_live)


class ExpiredLinksAreNotOfferedTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.patcher = paystack_returns_a_url()
        self.addCleanup(self.patcher.stop)
        self.customer = User.objects.create_user(
            "amina", "amina@example.com", "pw"
        )
        Group.objects.get_or_create(name="Customer")[0].user_set.add(self.customer)
        self.payment = a_payment(order=an_order(customer=self.customer))
        dispatch_payment(self.payment, email="amina@example.com")
        self.payment.refresh_from_db()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.customer).key}"
        )

    def expire_it(self):
        Payment.objects.filter(pk=self.payment.pk).update(
            checkout_expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.payment.refresh_from_db()

    def test_a_live_link_is_handed_out(self):
        data = PaymentSerializer(self.payment).data

        self.assertEqual(data["checkout_url"], "https://checkout.paystack.com/abc123")
        self.assertTrue(data["checkout_is_live"])

    def test_an_expired_link_is_withheld(self):
        """A link on screen is one somebody will click. The honest offer once
        it has lapsed is a fresh one, not a struck-through old one."""
        self.expire_it()

        data = PaymentSerializer(self.payment).data

        self.assertIsNone(data["checkout_url"])
        self.assertFalse(data["checkout_is_live"])

    def test_the_customers_own_list_withholds_it_too(self):
        self.expire_it()

        rows = self.client.get("/api/payments/mine/").data["results"]

        self.assertIsNone(rows[0]["checkout_url"])

    def test_they_can_ask_for_another(self):
        self.expire_it()

        response = self.client.post(
            f"/api/payments/mine/{self.payment.reference}/pay/"
        )

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertTrue(self.payment.checkout_is_live)


class TheEmailCarriesOurLinkTests(TestCase):
    """The lifetime is not mentioned to the customer any more, because it no
    longer applies to anything they hold. What they get is our link; the ten
    minutes govern the Paystack session it mints when they open it."""

    def setUp(self):
        self.patcher = paystack_returns_a_url()
        self.addCleanup(self.patcher.stop)

    def test_the_email_sends_them_to_us_not_to_paystack(self):
        payment = a_payment()
        dispatch_payment(payment, email="amina@example.com")

        from django.core import mail

        mail.outbox = []
        send_payment_instructions(payment, "amina@example.com")

        self.assertIn(f"/pay/{payment.reference}/", mail.outbox[0].body)
        self.assertNotIn("checkout.paystack.com", mail.outbox[0].body)
