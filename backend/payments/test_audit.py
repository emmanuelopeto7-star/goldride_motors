"""The history behind a payment, and the two ways it gets written.

A payment's status is now written in exactly one place, and every write leaves
a record of what changed it. That matters for a reason that is not obvious from
the row: a payment reading `failed` could have been failed by Paystack, by the
sweep, or by a manager at four in the afternoon, and those are three different
conversations to have with a customer.

The other half is that the sweep now runs itself. The tests here are the ones
that would catch it running twice, running against payments somebody is still
paying for, or taking the process down when a provider is unreachable.
"""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Payment, PaymentEvent, ReconciliationRun
from .sweeper import sweep
from .tests import a_payment, an_order, paystack_success

User = get_user_model()

SECRET = "sk_test_pretend"
WEBHOOK = "/api/payments/webhook/"
CALLBACK = "/api/payments/mpesa/callback/"


def staff(username, role):
    user = User.objects.create_user(username, f"{username}@goldride.co.ke", "pw")
    Group.objects.get_or_create(name=role)[0].user_set.add(user)
    return user


def age(payment, minutes):
    """Push a payment back in time, past the sweep's stale window."""
    Payment.objects.filter(pk=payment.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes)
    )
    payment.refresh_from_db()
    return payment


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class EveryPathLeavesAHistoryTests(APITestCase):
    """Four pieces of code settle payments. All four must be traceable."""

    def setUp(self):
        cache.clear()

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    @patch("payments.views.verify_paystack_payment")
    def test_a_webhook_says_it_was_a_webhook(self, verify):
        verify.return_value = paystack_success()
        payment = a_payment(paystack_ref="ps-ref-1")
        body = {"event": "charge.success", "data": {"reference": "ps-ref-1"}}
        raw = json.dumps(body).encode()

        self.client.post(
            WEBHOOK,
            data=raw,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=hmac.new(
                SECRET.encode(), raw, hashlib.sha512
            ).hexdigest(),
        )

        event = payment.events.get()
        self.assertEqual(event.source, PaymentEvent.WEBHOOK)
        self.assertEqual((event.from_status, event.to_status), ("pending", "paid"))
        self.assertIsNone(event.actor)

    @patch("payments.views.query_mpesa_payment")
    def test_a_callback_says_it_was_a_callback(self, query):
        query.return_value = {"ResultCode": 0}
        payment = a_payment(method="mpesa", checkout_request_id="ws_CO_1")

        self.client.post(
            CALLBACK,
            {
                "Body": {
                    "stkCallback": {
                        "CheckoutRequestID": "ws_CO_1",
                        "CallbackMetadata": {
                            "Item": [
                                {"Name": "MpesaReceiptNumber", "Value": "QGR1234"}
                            ]
                        },
                    }
                }
            },
            format="json",
        )

        event = payment.events.get()
        self.assertEqual(event.source, PaymentEvent.CALLBACK)
        self.assertIn("QGR1234", event.detail)

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_the_sweep_says_it_was_the_sweep(self, verify):
        verify.return_value = paystack_success()
        payment = age(a_payment(paystack_ref="ps-ref-2"), minutes=10)

        sweep(trigger=ReconciliationRun.COMMAND)

        event = payment.events.get()
        self.assertEqual(event.source, PaymentEvent.RECONCILE)
        self.assertIsNone(event.actor)

    def test_a_bank_transfer_names_the_person_who_believed_it(self):
        """The only evidence a manual payment has is who said so."""
        boss = staff("boss", "Manager")
        self.sign_in(boss)
        payment = a_payment(method="manual")

        response = self.client.post(
            f"/api/staff/payments/{payment.reference}/record/",
            {"provider_ref": "FT2408271", "note": "seen on the statement"},
        )

        self.assertEqual(response.status_code, 200)
        event = payment.events.get()
        self.assertEqual(event.source, PaymentEvent.RECORDED)
        self.assertEqual(event.actor, boss)
        self.assertIn("FT2408271", event.detail)

    @patch("payments.views.verify_paystack_payment")
    def test_a_replayed_webhook_adds_no_second_line(self, verify):
        verify.return_value = paystack_success()
        payment = a_payment(paystack_ref="ps-ref-3")
        body = {"event": "charge.success", "data": {"reference": "ps-ref-3"}}
        raw = json.dumps(body).encode()
        signature = hmac.new(SECRET.encode(), raw, hashlib.sha512).hexdigest()

        for _ in range(2):
            self.client.post(
                WEBHOOK,
                data=raw,
                content_type="application/json",
                HTTP_X_PAYSTACK_SIGNATURE=signature,
            )

        self.assertEqual(payment.events.count(), 1)


class CorrectingAPaymentTests(APITestCase):
    """The one endpoint that overrules a provider."""

    def setUp(self):
        cache.clear()
        self.boss = staff("boss", "Manager")
        self.payment = a_payment(status="paid")
        self.url = f"/api/staff/payments/{self.payment.reference}/correct/"
        self.sign_in(self.boss)

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def test_sales_cannot_correct_a_payment(self):
        self.sign_in(staff("asha", "Sales"))

        response = self.client.post(
            self.url, {"status": "refunded", "reason": "refunded at the bank"}
        )

        self.assertEqual(response.status_code, 403)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "paid")

    def test_a_manager_can_move_it_out_of_any_state(self):
        # Settling is only ever pending -> something. A correction is the
        # opposite: it exists for the states the rails already decided.
        response = self.client.post(
            self.url, {"status": "refunded", "reason": "refunded at the bank"}
        )

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "refunded")

    def test_the_correction_is_recorded_against_whoever_made_it(self):
        self.client.post(
            self.url, {"status": "failed", "reason": "money never arrived"}
        )

        event = self.payment.events.get()
        self.assertEqual(event.source, PaymentEvent.CORRECTION)
        self.assertEqual(event.actor, self.boss)
        self.assertEqual((event.from_status, event.to_status), ("paid", "failed"))
        self.assertEqual(event.detail, "money never arrived")

    def test_a_reason_is_required(self):
        """"Fixed" six months later tells the next reader nothing."""
        response = self.client.post(self.url, {"status": "failed", "reason": "oops"})

        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "paid")

    def test_correcting_to_the_state_it_is_already_in_is_refused(self):
        response = self.client.post(
            self.url, {"status": "paid", "reason": "no change at all"}
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.payment.events.count(), 0)

    def test_nothing_is_ever_deleted(self):
        self.client.post(self.url, {"status": "failed", "reason": "money never came"})
        self.client.post(self.url, {"status": "paid", "reason": "it did arrive, late"})

        self.assertEqual(
            [(e.from_status, e.to_status) for e in self.payment.events.all()],
            [("paid", "failed"), ("failed", "paid")],
        )


class ReadingTheRecordsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.payment = a_payment()
        PaymentEvent.objects.create(
            payment=self.payment,
            from_status="pending",
            to_status="paid",
            source=PaymentEvent.WEBHOOK,
            detail="Paystack charge.success",
        )
        self.url = f"/api/staff/payments/{self.payment.reference}/history/"

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def test_a_stranger_cannot_read_a_payment_history(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_a_customer_cannot_read_a_payment_history(self):
        buyer = User.objects.create_user("buyer", "buyer@example.com", "pw")
        Group.objects.get_or_create(name="Customer")[0].user_set.add(buyer)
        self.sign_in(buyer)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_sales_can_read_it_even_though_they_cannot_correct(self):
        # An agent fielding "I paid on Tuesday" needs the history to answer it.
        self.sign_in(staff("asha", "Sales"))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["events"][0]["source"], PaymentEvent.WEBHOOK)
        self.assertEqual(
            response.data["events"][0]["source_label"], "Paystack webhook"
        )

    def test_staff_can_see_whether_the_sweep_is_alive(self):
        self.sign_in(staff("asha", "Sales"))
        sweep(trigger=ReconciliationRun.COMMAND)

        response = self.client.get("/api/staff/payments/reconciliation-runs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["runs"][0]["state"], ReconciliationRun.DONE)
        self.assertIn("interval_minutes", response.data)


class TheSweepTests(APITestCase):
    def setUp(self):
        cache.clear()

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_it_leaves_a_payment_somebody_is_still_paying_alone(self, verify):
        """Nobody has finished a checkout thirty seconds after raising it."""
        verify.return_value = paystack_success()
        a_payment(paystack_ref="ps-fresh")

        run = sweep(trigger=ReconciliationRun.COMMAND, stale_minutes=5)

        self.assertEqual(run.checked, 0)
        verify.assert_not_called()

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_it_records_what_it_did(self, verify):
        verify.return_value = paystack_success()
        age(a_payment(paystack_ref="ps-old"), minutes=30)

        run = sweep(trigger=ReconciliationRun.COMMAND)

        self.assertEqual(run.state, ReconciliationRun.DONE)
        self.assertEqual(run.checked, 1)
        self.assertEqual(run.updated, 1)
        self.assertIsNotNone(run.finished_at)

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_a_second_sweep_stands_down_rather_than_queueing(self, verify):
        """Four workers all run this thread. One should sweep, not four."""
        verify.return_value = paystack_success()
        ReconciliationRun.objects.create(
            trigger=ReconciliationRun.AUTOMATIC, state=ReconciliationRun.RUNNING
        )
        age(a_payment(paystack_ref="ps-old-2"), minutes=30)

        run = sweep(trigger=ReconciliationRun.COMMAND)

        self.assertEqual(run.checked, 0)
        self.assertIn("already running", run.error)
        verify.assert_not_called()

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_an_abandoned_sweep_does_not_block_the_next_one_forever(self, verify):
        # A process killed mid-sweep leaves its row open. After twice the
        # interval it is assumed dead rather than busy.
        verify.return_value = paystack_success()
        stale = ReconciliationRun.objects.create(
            trigger=ReconciliationRun.AUTOMATIC, state=ReconciliationRun.RUNNING
        )
        ReconciliationRun.objects.filter(pk=stale.pk).update(
            started_at=timezone.now() - timedelta(hours=8)
        )
        age(a_payment(paystack_ref="ps-old-3"), minutes=30)

        run = sweep(trigger=ReconciliationRun.COMMAND)

        self.assertEqual(run.checked, 1)

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_a_provider_outage_is_recorded_rather_than_raised(self, verify):
        """The site must keep selling cars while Paystack is down."""
        verify.side_effect = RuntimeError("paystack is unreachable")
        age(a_payment(paystack_ref="ps-old-4"), minutes=30)

        run = sweep(trigger=ReconciliationRun.COMMAND)

        self.assertEqual(run.state, ReconciliationRun.FAILED)
        self.assertIn("unreachable", run.error)


class TheCustomersPageTests(APITestCase):
    """It used to reconcile inline, which made a page load wait on Paystack."""

    def setUp(self):
        cache.clear()
        self.buyer = User.objects.create_user("buyer", "buyer@example.com", "pw")
        Group.objects.get_or_create(name="Customer")[0].user_set.add(self.buyer)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.buyer).key}"
        )
        order = an_order(customer=self.buyer)
        self.payment = a_payment(order=order, paystack_ref="ps-mine")

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_listing_payments_asks_no_provider_anything(self, verify):
        response = self.client.get("/api/payments/mine/")

        self.assertEqual(response.status_code, 200)
        verify.assert_not_called()

    def test_they_still_see_their_own_payments(self):
        response = self.client.get("/api/payments/mine/")

        references = [row["reference"] for row in response.data["results"]]
        self.assertIn(str(self.payment.reference), references)
