"""What the money endpoints must never get wrong.

These four properties were proven by hand against the Paystack and Daraja
sandboxes in July and have been protected by nothing since:

  * a webhook is only believed after re-querying the provider
  * a replayed webhook cannot pay an invoice twice
  * a forged signature is refused
  * everything except a bad signature answers 2xx, or the provider retries
    the same delivery forever

The providers are mocked at the module boundary - these tests are about our
decisions, not about requests.
"""
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from imports.models import ImportOrder

from .models import Payment
from .reconciliation import ABANDONED_GRACE, reconcile_payment
from .services import verify_paystack_signature

SECRET = "sk_test_pretend"
WEBHOOK = "/api/payments/webhook/"
CALLBACK = "/api/payments/mpesa/callback/"


def an_order(**overrides):
    fields = {
        "customer_name": "Amina Otieno",
        "phone": "0712345678",
        "car_description": "Toyota Land Cruiser (2021)",
        "total_amount": Decimal("5000.00"),
    }
    fields.update(overrides)
    return ImportOrder.objects.create(**fields)


def a_payment(order=None, **overrides):
    fields = {
        "order": order or an_order(),
        "amount": Decimal("5000.00"),
        "method": "card",
        "status": "pending",
    }
    fields.update(overrides)
    return Payment.objects.create(**fields)


def paystack_success(amount_cents=500000, transaction_id=99001):
    return {"status": "success", "amount": amount_cents, "id": transaction_id}


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class PaystackWebhookTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.payment = a_payment(paystack_ref="ps-ref-1")

    def deliver(self, body=None, signature=None, reference="ps-ref-1", event="charge.success"):
        """Post a webhook, signed correctly unless told otherwise."""
        if body is None:
            body = {"event": event, "data": {"reference": reference, "amount": 500000}}
        raw = json.dumps(body).encode()

        if signature is None:
            signature = hmac.new(SECRET.encode(), raw, hashlib.sha512).hexdigest()

        return self.client.post(
            WEBHOOK,
            data=raw,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

    # --- the happy path ----------------------------------------------------

    @patch("payments.views.verify_paystack_payment")
    def test_a_verified_charge_is_paid(self, verify):
        verify.return_value = paystack_success()

        response = self.deliver()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "paid")
        self.assertEqual(self.payment.provider_ref, "99001")
        # the reference in the body is never trusted on its own
        verify.assert_called_once_with("ps-ref-1")

    # --- the four hand-proven refusals -------------------------------------

    @patch("payments.views.verify_paystack_payment")
    def test_a_forged_signature_is_refused(self, verify):
        response = self.deliver(signature="0" * 128)

        self.assertEqual(response.status_code, 400)
        verify.assert_not_called()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    @patch("payments.views.verify_paystack_payment")
    def test_a_missing_signature_is_refused(self, verify):
        raw = json.dumps({"event": "charge.success", "data": {"reference": "ps-ref-1"}})
        response = self.client.post(WEBHOOK, data=raw, content_type="application/json")

        self.assertEqual(response.status_code, 400)
        verify.assert_not_called()

    @patch("payments.views.verify_paystack_payment")
    def test_a_tampered_body_no_longer_matches_its_signature(self, verify):
        honest = json.dumps(
            {"event": "charge.success", "data": {"reference": "ps-ref-1", "amount": 500000}}
        ).encode()
        signature = hmac.new(SECRET.encode(), honest, hashlib.sha512).hexdigest()
        tampered = honest.replace(b"500000", b"100000")

        response = self.client.post(
            WEBHOOK,
            data=tampered,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, 400)
        verify.assert_not_called()

    @patch("payments.views.verify_paystack_payment")
    def test_a_replay_cannot_pay_twice(self, verify):
        verify.return_value = paystack_success()
        self.deliver()

        second = self.deliver()

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "no pending payment")
        self.assertEqual(Payment.objects.filter(status="paid").count(), 1)

    @patch("payments.views.verify_paystack_payment")
    def test_a_failed_charge_claiming_success_is_refused(self, verify):
        """A signed body saying charge.success proves nothing about the money."""
        verify.return_value = {"status": "failed", "amount": 500000, "id": 1}

        response = self.deliver()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "not successful")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    # --- everything else ---------------------------------------------------

    @patch("payments.views.verify_paystack_payment")
    def test_the_provider_is_believed_over_the_body_about_the_amount(self, verify):
        # the body claims the right amount; the re-query disagrees
        verify.return_value = paystack_success(amount_cents=100000)

        response = self.deliver()

        self.assertEqual(response.json()["status"], "amount mismatch")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")
        self.assertEqual(self.payment.note, "amount mismatch")

    @patch("payments.views.verify_paystack_payment")
    def test_an_unverifiable_charge_is_left_alone(self, verify):
        verify.return_value = None

        response = self.deliver()

        self.assertEqual(response.json()["status"], "could not verify")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    @patch("payments.views.verify_paystack_payment")
    def test_other_events_are_ignored_without_a_re_query(self, verify):
        response = self.deliver(event="charge.dispute.create")

        self.assertEqual(response.json()["status"], "ignored")
        verify.assert_not_called()

    @patch("payments.views.verify_paystack_payment")
    def test_a_body_without_a_reference_is_ignored(self, verify):
        response = self.deliver(body={"event": "charge.success", "data": {}})

        self.assertEqual(response.json()["status"], "ignored")
        verify.assert_not_called()

    @patch("payments.views.verify_paystack_payment")
    def test_our_own_reference_is_not_a_way_in(self, verify):
        """Paystack refs are per-attempt; our reference must not match one.

        Looking up by Payment.reference is what the duplicate_reference fix
        moved away from - a webhook quoting it must find nothing.
        """
        verify.return_value = paystack_success()

        response = self.deliver(reference=str(self.payment.reference))

        self.assertEqual(response.json()["status"], "no pending payment")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    @patch("payments.views.verify_paystack_payment")
    def test_an_unknown_reference_changes_nothing(self, verify):
        verify.return_value = paystack_success()

        response = self.deliver(reference="ps-ref-somebody-else")

        self.assertEqual(response.json()["status"], "no pending payment")
        self.assertEqual(Payment.objects.filter(status="paid").count(), 0)

    @patch("payments.views.verify_paystack_payment")
    def test_only_a_bad_signature_is_ever_non_2xx(self, verify):
        """Any other non-2xx and Paystack retries the same delivery forever."""
        cases = [
            ({"status": "failed", "amount": 500000, "id": 1}, "ps-ref-1"),
            (paystack_success(amount_cents=1), "ps-ref-1"),
            (paystack_success(), "ps-ref-unknown"),
            (None, "ps-ref-1"),
        ]

        for verified, reference in cases:
            with self.subTest(reference=reference, verified=verified):
                verify.return_value = verified
                response = self.deliver(reference=reference)
                self.assertLess(response.status_code, 300)

        # and the malformed ones, which never reach the provider at all
        for body in [{}, {"event": "charge.success"}, {"data": {"reference": "x"}}]:
            with self.subTest(body=body):
                self.assertLess(self.deliver(body=body).status_code, 300)


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class PaystackSignatureTests(APITestCase):
    def test_a_correct_signature_passes(self):
        body = b'{"event":"charge.success"}'
        signature = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()

        self.assertTrue(verify_paystack_signature(body, signature))

    def test_everything_else_fails(self):
        body = b'{"event":"charge.success"}'
        signature = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()

        self.assertFalse(verify_paystack_signature(body, None))
        self.assertFalse(verify_paystack_signature(body, ""))
        self.assertFalse(verify_paystack_signature(body, "nonsense"))
        self.assertFalse(verify_paystack_signature(body, signature[:-1] + "0"))
        self.assertFalse(verify_paystack_signature(b'{"event":"other"}', signature))

    def test_a_signature_from_a_different_key_fails(self):
        body = b'{"event":"charge.success"}'
        wrong = hmac.new(b"sk_test_somebody_else", body, hashlib.sha512).hexdigest()

        self.assertFalse(verify_paystack_signature(body, wrong))


class MpesaCallbackTests(APITestCase):
    """Daraja does not sign anything, so the callback is only a nudge to ask."""

    def setUp(self):
        cache.clear()
        self.payment = a_payment(method="mpesa", checkout_request_id="ws_CO_1")

    def deliver(self, checkout_id="ws_CO_1", result_code=0, receipt="QK12AB34CD"):
        body = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": result_code,
                    "CallbackMetadata": {
                        "Item": [{"Name": "MpesaReceiptNumber", "Value": receipt}]
                    },
                }
            }
        }
        if checkout_id is None:
            del body["Body"]["stkCallback"]["CheckoutRequestID"]
        return self.client.post(CALLBACK, body, format="json")

    @patch("payments.views.query_mpesa_payment")
    def test_a_confirmed_push_is_paid(self, query):
        query.return_value = {"ResultCode": "0", "ResultDesc": "Accepted"}

        response = self.deliver()

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "paid")
        self.assertEqual(self.payment.provider_ref, "QK12AB34CD")
        query.assert_called_once_with("ws_CO_1")

    @patch("payments.views.query_mpesa_payment")
    def test_a_forged_success_is_refused(self, query):
        """Proven by hand in July: a fake ResultCode 0 through the tunnel."""
        query.return_value = {"ResultCode": "1032", "ResultDesc": "Cancelled by user"}

        response = self.deliver(result_code=0)

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    @patch("payments.views.query_mpesa_payment")
    def test_an_unanswerable_query_leaves_it_pending(self, query):
        query.return_value = None

        self.deliver()

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    @patch("payments.views.query_mpesa_payment")
    def test_an_unknown_checkout_id_is_not_even_queried(self, query):
        response = self.deliver(checkout_id="ws_CO_somebody_else")

        self.assertEqual(response.status_code, 200)
        query.assert_not_called()
        self.assertEqual(Payment.objects.filter(status="paid").count(), 0)

    @patch("payments.views.query_mpesa_payment")
    def test_a_callback_without_a_checkout_id_is_accepted(self, query):
        response = self.deliver(checkout_id=None)

        self.assertEqual(response.status_code, 200)
        query.assert_not_called()

    @patch("payments.views.query_mpesa_payment")
    def test_a_replay_cannot_pay_twice(self, query):
        query.return_value = {"ResultCode": "0"}
        self.deliver()
        query.reset_mock()

        self.deliver(receipt="DIFFERENT")

        query.assert_not_called()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.provider_ref, "QK12AB34CD")

    @patch("payments.views.query_mpesa_payment")
    def test_daraja_always_gets_result_code_zero(self, query):
        """A non-zero answer makes Safaricom retry the callback."""
        for outcome in [{"ResultCode": "0"}, {"ResultCode": "1032"}, None]:
            with self.subTest(outcome=outcome):
                query.return_value = outcome
                response = self.deliver()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["ResultCode"], 0)


class CardReconciliationTests(APITestCase):
    """The safety net that caught two real payments the webhook missed."""

    def setUp(self):
        self.payment = a_payment(paystack_ref="ps-ref-1")

    def age(self, payment, minutes):
        Payment.objects.filter(pk=payment.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes)
        )
        payment.refresh_from_db()

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_a_success_the_webhook_missed_is_caught(self, verify):
        verify.return_value = paystack_success()

        changed, message = reconcile_payment(self.payment)

        self.assertTrue(changed)
        self.assertEqual(message, "paid")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "paid")
        self.assertEqual(self.payment.provider_ref, "99001")

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_a_live_checkout_is_not_failed_inside_the_grace_window(self, verify):
        """Paystack calls an unpaid checkout 'abandoned' the instant it opens."""
        verify.return_value = {"status": "abandoned"}

        changed, message = reconcile_payment(self.payment)

        self.assertFalse(changed)
        self.assertEqual(message, "checkout still open")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_an_abandoned_checkout_fails_once_the_window_passes(self, verify):
        verify.return_value = {"status": "abandoned"}
        self.age(self.payment, int(ABANDONED_GRACE.total_seconds() // 60) + 1)

        changed, _ = reconcile_payment(self.payment)

        self.assertTrue(changed)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        self.assertEqual(self.payment.note, "abandoned")

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_a_success_for_the_wrong_amount_is_not_paid(self, verify):
        verify.return_value = paystack_success(amount_cents=100000)

        changed, _ = reconcile_payment(self.payment)

        self.assertTrue(changed)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        self.assertEqual(self.payment.note, "amount mismatch")

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_a_payment_that_was_never_initiated_is_not_queried(self, verify):
        never = a_payment(paystack_ref="")

        changed, message = reconcile_payment(never)

        self.assertFalse(changed)
        self.assertEqual(message, "never initiated")
        verify.assert_not_called()

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_a_settled_payment_is_left_alone(self, verify):
        self.payment.status = "paid"
        self.payment.save()

        changed, message = reconcile_payment(self.payment)

        self.assertFalse(changed)
        self.assertEqual(message, "not pending")
        verify.assert_not_called()

    @patch("payments.reconciliation.verify_paystack_payment")
    def test_an_unrecognised_state_changes_nothing(self, verify):
        verify.return_value = {"status": "ongoing"}

        changed, message = reconcile_payment(self.payment)

        self.assertFalse(changed)
        self.assertIn("ongoing", message)


class MpesaReconciliationTests(APITestCase):
    def setUp(self):
        self.payment = a_payment(method="mpesa", checkout_request_id="ws_CO_1")

    @patch("payments.reconciliation.query_mpesa_payment")
    def test_a_completed_push_is_paid(self, query):
        query.return_value = {"ResultCode": 0, "ResultDesc": "Success"}

        changed, _ = reconcile_payment(self.payment)

        self.assertTrue(changed)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "paid")

    @patch("payments.reconciliation.query_mpesa_payment")
    def test_a_cancelled_push_fails(self, query):
        query.return_value = {"ResultCode": 1032, "ResultDesc": "Cancelled by user"}

        changed, _ = reconcile_payment(self.payment)

        self.assertTrue(changed)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "failed")
        self.assertEqual(self.payment.note, "Cancelled by user")

    @patch("payments.reconciliation.query_mpesa_payment")
    def test_a_push_still_in_flight_is_left_pending(self, query):
        query.return_value = {"ResultCode": 500, "ResultDesc": "Processing"}

        changed, message = reconcile_payment(self.payment)

        self.assertFalse(changed)
        self.assertIn("500", message)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    @patch("payments.reconciliation.query_mpesa_payment")
    def test_a_push_that_was_never_sent_is_not_queried(self, query):
        never = a_payment(method="mpesa", checkout_request_id="")

        changed, message = reconcile_payment(never)

        self.assertFalse(changed)
        self.assertEqual(message, "never pushed")
        query.assert_not_called()

    def test_a_manual_payment_is_left_to_staff(self):
        manual = a_payment(method="manual")

        changed, message = reconcile_payment(manual)

        self.assertFalse(changed)
        self.assertEqual(message, "manual - staff decides")


class InitiatePaymentTests(APITestCase):
    """The server decides the amount - the client only names the invoice."""

    URL = "/api/payments/initiate/"

    def setUp(self):
        cache.clear()
        self.payment = a_payment()

    @patch("payments.services.requests.post")
    def test_the_amount_comes_from_the_database(self, post):
        post.return_value.json.return_value = {
            "status": True,
            "data": {"authorization_url": "https://checkout.paystack.com/abc"},
        }

        response = self.client.post(
            self.URL,
            {
                "reference": str(self.payment.reference),
                "email": "amina@example.com",
                "amount": 1,  # ignored
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(post.call_args.kwargs["json"]["amount"], 500000)

    @patch("payments.services.requests.post")
    def test_each_attempt_gets_a_fresh_paystack_reference(self, post):
        """Paystack refuses a reused reference, which used to brick an invoice."""
        post.return_value.json.return_value = {
            "status": True,
            "data": {"authorization_url": "https://checkout.paystack.com/abc"},
        }
        body = {"reference": str(self.payment.reference), "email": "amina@example.com"}

        self.client.post(self.URL, body, format="json")
        self.payment.refresh_from_db()
        first = self.payment.paystack_ref

        self.client.post(self.URL, body, format="json")
        self.payment.refresh_from_db()

        self.assertTrue(first)
        self.assertNotEqual(first, self.payment.paystack_ref)
        # and neither of them is the reference we show the customer
        self.assertNotEqual(first, str(self.payment.reference))

    @patch("payments.services.requests.post")
    def test_a_refusal_from_paystack_is_reported(self, post):
        post.return_value.json.return_value = {
            "status": False,
            "message": "Amount cannot be processed online",
        }

        response = self.client.post(
            self.URL,
            {"reference": str(self.payment.reference), "email": "amina@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)

    def test_an_unknown_reference_is_refused(self):
        import uuid

        response = self.client.post(
            self.URL,
            {"reference": str(uuid.uuid4()), "email": "amina@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_a_settled_invoice_cannot_be_re_initiated(self):
        self.payment.status = "paid"
        self.payment.save()

        response = self.client.post(
            self.URL,
            {"reference": str(self.payment.reference), "email": "amina@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_the_required_fields_are_required(self):
        for body in [{}, {"reference": str(self.payment.reference)}, {"email": "a@b.com"}]:
            with self.subTest(body=body):
                response = self.client.post(self.URL, body, format="json")
                self.assertEqual(response.status_code, 400)
