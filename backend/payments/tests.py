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

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.cache import cache
from django.test import TestCase as DjangoTestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from cars.models import Car
from imports.models import ImportOrder

from .models import Payment
from .mpesa import start_mpesa_payment, whole_shillings
from .notifications import send_payment_instructions
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
    """The server decides the amount, and whose invoice it is.

    The client names an invoice it already owns; everything else - the sum,
    the address the receipt goes to - comes from the database and the signed-in
    account.
    """

    URL = "/api/payments/initiate/"

    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.customer = User.objects.create_user(
            "amina", "amina@example.com", "pw"
        )
        Group.objects.get_or_create(name="Customer")[0].user_set.add(self.customer)
        self.payment = a_payment(order=an_order(customer=self.customer))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.customer).key}"
        )

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
                "email": "someone-else@example.com",  # ignored
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
        body = {"reference": str(self.payment.reference)}

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
            {"reference": str(self.payment.reference)},
            format="json",
        )

        self.assertEqual(response.status_code, 502)

    def test_an_unknown_reference_is_refused(self):
        import uuid

        response = self.client.post(
            self.URL,
            {"reference": str(uuid.uuid4())},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_a_settled_invoice_cannot_be_re_initiated(self):
        self.payment.status = "paid"
        self.payment.save()

        response = self.client.post(
            self.URL,
            {"reference": str(self.payment.reference)},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_a_reference_is_required(self):
        """The email used to be required too - and was the hole: it named
        where the receipt went, and the caller chose it."""
        response = self.client.post(self.URL, {}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_the_receipt_goes_to_the_account_not_the_request(self, ):
        with patch("payments.services.requests.post") as post:
            post.return_value.json.return_value = {
                "status": True,
                "data": {"authorization_url": "https://checkout.paystack.com/abc"},
            }

            self.client.post(
                self.URL,
                {
                    "reference": str(self.payment.reference),
                    "email": "attacker@example.com",
                },
                format="json",
            )

        self.assertEqual(post.call_args.kwargs["json"]["email"], "amina@example.com")

    def test_a_stranger_cannot_start_a_checkout(self):
        self.client.credentials()

        response = self.client.post(
            self.URL, {"reference": str(self.payment.reference)}, format="json"
        )

        self.assertIn(response.status_code, (401, 403))

    def test_another_customers_invoice_is_not_found(self):
        """Not "forbidden" - a reference that is not yours must look exactly
        like one that does not exist, or the endpoint becomes an oracle."""
        User = get_user_model()
        nosy = User.objects.create_user("nosy", "nosy@example.com", "pw")
        Group.objects.get_or_create(name="Customer")[0].user_set.add(nosy)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=nosy).key}"
        )

        response = self.client.post(
            self.URL, {"reference": str(self.payment.reference)}, format="json"
        )

        self.assertEqual(response.status_code, 404)


class CheckoutNotificationTests(APITestCase):
    """The link used to stop at the API response.

    Paystack's initialize call returns an authorization URL and contacts
    nobody, so an approved customer only found their link by signing in and
    hunting for it. Approval is the moment they are waiting on.
    """

    def test_a_card_payment_emails_the_link(self):
        payment = a_payment(method="card")
        payment.checkout_url = "https://checkout.paystack.com/abc123"
        payment.save(update_fields=["checkout_url"])
        mail.outbox.clear()

        sent = send_payment_instructions(payment, "buyer@example.com")

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["buyer@example.com"])
        self.assertIn(f"/pay/{payment.reference}/", mail.outbox[0].body)

    def test_an_mpesa_payment_points_at_the_phone_prompt(self):
        """There is no link to send - the STK push is the delivery."""
        payment = a_payment(method="mpesa")
        mail.outbox.clear()

        send_payment_instructions(payment, "buyer@example.com")

        self.assertIn("M-PESA prompt", mail.outbox[0].body)

    def test_a_manual_payment_says_why_and_what_happens_next(self):
        """The common case on this inventory, and the one most needing an email."""
        payment = a_payment(method="manual")
        payment.note = "online payment unavailable: amount too large"
        payment.save(update_fields=["note"])
        mail.outbox.clear()

        send_payment_instructions(payment, "buyer@example.com")

        body = mail.outbox[0].body
        self.assertIn("bank transfer", body)
        self.assertIn("amount too large", body)

    def test_a_card_payment_is_worth_mailing_before_any_checkout_exists(self):
        """This used to be refused, and was right to be: the email carried a
        Paystack session, and mailing "pay here" with no here was worse than
        silence. The link is ours now and mints a session when opened, so
        there is something to send even when dispatch never ran."""
        payment = a_payment(method="card")
        mail.outbox.clear()

        sent = send_payment_instructions(payment, "buyer@example.com")

        self.assertTrue(sent)
        self.assertIn(f"/pay/{payment.reference}/", mail.outbox[0].body)

    def test_no_address_means_no_send(self):
        payment = a_payment(method="mpesa")
        mail.outbox.clear()

        sent = send_payment_instructions(payment, "")

        self.assertFalse(sent)
        self.assertEqual(len(mail.outbox), 0)

    def test_sending_is_stamped_on_the_payment(self):
        """Staff need to tell "waiting on them" from "waiting on us"."""
        payment = a_payment(method="mpesa")
        self.assertIsNone(payment.checkout_sent_at)

        send_payment_instructions(payment, "buyer@example.com")

        payment.refresh_from_db()
        self.assertIsNotNone(payment.checkout_sent_at)

    def test_nothing_is_stamped_when_nothing_was_sent(self):
        """A manual payment with no note has nothing useful to say, so no
        email goes and the stamp stays clear - that is still the difference
        between "waiting on them" and "waiting on us"."""
        payment = a_payment(method="manual")

        with patch("payments.notifications._how_to_pay", return_value=None):
            send_payment_instructions(payment, "buyer@example.com")

        payment.refresh_from_db()
        self.assertIsNone(payment.checkout_sent_at)

    def test_the_email_carries_the_tracking_link(self):
        payment = a_payment(method="mpesa")
        mail.outbox.clear()

        send_payment_instructions(payment, "buyer@example.com")

        self.assertIn(str(payment.order.token), mail.outbox[0].body)

    def test_the_subject_uses_a_readable_car_name(self):
        """Derived from the car, not from whatever car_description holds - old
        orders still carry the blob the previous Car.__str__ wrote."""
        car = Car.objects.create(
            make="Toyota",
            model="Prado",
            year=2020,
            price=Decimal("8900000.00"),
            description="A very long description " * 20,
        )
        order = an_order(car=car, car_description="Toyota Prado - used - $8900000 - " + "blah " * 30)
        payment = a_payment(order=order, method="mpesa")
        mail.outbox.clear()

        send_payment_instructions(payment, "buyer@example.com")

        self.assertIn("2020 Toyota Prado", mail.outbox[0].subject)
        self.assertLess(len(mail.outbox[0].subject), 80)


class RaisingAPaymentTests(APITestCase):
    """Staff putting a figure in front of a customer by hand.

    Most invoices are raised for us when a purchase is approved. This is the
    rest of the business - a balance, a second instalment, an order that was
    never a purchase request - and it is the one path where the amount is
    typed by a person, so it is the one that needs guarding.
    """

    URL = "/api/staff/payments/"

    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.order = an_order(total_amount=Decimal("900000.00"))

        self.manager = User.objects.create_user("boss", "boss@example.com", "pw")
        Group.objects.get_or_create(name="Manager")[0].user_set.add(self.manager)
        self.sales = User.objects.create_user("rep", "rep@example.com", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(self.sales)

        self.as_manager()

    def as_manager(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.manager).key}"
        )

    def as_sales(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.sales).key}"
        )

    def raise_payment(self, **overrides):
        body = {
            "order": self.order.id,
            "amount": "300000.00",
            "method": "mpesa",
        }
        body.update(overrides)
        return self.client.post(self.URL, body, format="json")

    def test_a_manager_can_raise_one(self):
        response = self.raise_payment(note="Deposit agreed on the phone")

        self.assertEqual(response.status_code, 201)
        payment = Payment.objects.get(reference=response.data["reference"])
        self.assertEqual(payment.order, self.order)
        self.assertEqual(payment.amount, Decimal("300000.00"))
        self.assertEqual(payment.note, "Deposit agreed on the phone")

    def test_it_starts_pending_and_nobody_has_been_asked_yet(self):
        """Raising is not collecting. Dispatch is a separate, deliberate step."""
        response = self.raise_payment()

        payment = Payment.objects.get(reference=response.data["reference"])
        self.assertEqual(payment.status, "pending")
        self.assertIsNone(payment.checkout_sent_at)
        self.assertEqual(payment.checkout_url, "")

    def test_sales_can_raise_one_too(self):
        """Collecting what a customer already agreed to owe is the job, not a
        decision about it - and what can be asked for is bounded by a total a
        manager set on the order."""
        self.as_sales()

        self.assertEqual(self.raise_payment().status_code, 201)

    def test_a_customer_cannot_raise_one_on_their_own_order(self):
        """The obvious way to turn an invoice into a discount."""
        User = get_user_model()
        buyer = User.objects.create_user("buyer", "buyer@example.com", "pw")
        Group.objects.get_or_create(name="Customer")[0].user_set.add(buyer)
        self.order.customer = buyer
        self.order.save(update_fields=["customer"])
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=buyer).key}"
        )

        self.assertEqual(self.raise_payment(amount="1.00").status_code, 403)
        self.assertFalse(Payment.objects.exists())

    def test_a_payment_cannot_be_marked_paid_by_hand(self):
        """Whether money arrived is the provider's answer, not ours. A hand-set
        `paid` would be a figure in the ledger no money ever matched."""
        response = self.raise_payment(status="paid")

        self.assertEqual(response.status_code, 201)
        payment = Payment.objects.get(reference=response.data["reference"])
        self.assertEqual(payment.status, "pending")

    def test_nothing_is_owed_on_a_cancelled_order(self):
        self.order.cancel(reason="changed their mind")

        response = self.raise_payment()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_zero_is_not_an_invoice(self):
        self.assertEqual(self.raise_payment(amount="0").status_code, 400)
        self.assertEqual(self.raise_payment(amount="-5000").status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_it_refuses_more_than_is_outstanding(self):
        """A typed amount is a mistyped amount. 9,000,000 for 900,000 should
        not reach a customer's phone."""
        response = self.raise_payment(amount="9000000.00")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Payment.objects.exists())

    def test_the_outstanding_figure_counts_what_has_been_paid(self):
        a_payment(order=self.order, amount=Decimal("800000.00"), status="paid")

        self.assertEqual(self.raise_payment(amount="100000.00").status_code, 201)
        self.assertEqual(self.raise_payment(amount="100000.01").status_code, 400)

    def test_an_order_with_no_agreed_total_is_left_to_the_person_typing(self):
        """A total of 0 means nothing was agreed, not that nothing is owed."""
        loose = an_order(total_amount=Decimal("0.00"))

        response = self.raise_payment(order=loose.id, amount="450000.00")

        self.assertEqual(response.status_code, 201)


class RecordingABankTransferTests(APITestCase):
    """The one payment nobody can be asked about.

    A card payment is believed after re-querying Paystack and an M-PESA one
    after re-querying Safaricom. A transfer into the bank account has no
    callback and no API - somebody reads a statement and says so. Until this
    endpoint the only way to close one was the Django admin, so a bank
    transfer raised in the dashboard had nowhere to end.
    """

    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.order = an_order(total_amount=Decimal("900000.00"))
        self.payment = a_payment(
            order=self.order, amount=Decimal("900000.00"), method="manual"
        )

        self.manager = User.objects.create_user("boss", "boss@example.com", "pw")
        Group.objects.get_or_create(name="Manager")[0].user_set.add(self.manager)
        self.sales = User.objects.create_user("rep", "rep@example.com", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(self.sales)
        self.as_manager()

    def url(self, payment=None):
        return f"/api/staff/payments/{(payment or self.payment).reference}/record/"

    def as_manager(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.manager).key}"
        )

    def as_sales(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.sales).key}"
        )

    def record(self, payment=None, **body):
        payload = {"provider_ref": "FT24081200123456"}
        payload.update(body)
        return self.client.post(self.url(payment), payload, format="json")

    def test_a_manager_can_record_it(self):
        response = self.record()

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "paid")
        self.assertEqual(self.payment.provider_ref, "FT24081200123456")

    def test_it_names_who_said_so(self):
        """No provider stands behind this one, so the person does."""
        self.record()

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.recorded_by, self.manager)
        self.assertIsNotNone(self.payment.recorded_at)

    def test_the_order_balance_moves(self):
        self.record()

        self.order.refresh_from_db()
        self.assertEqual(self.order.amount_paid, Decimal("900000.00"))
        self.assertTrue(self.order.is_settled)

    def test_the_bank_reference_is_required(self):
        """Without it there is nothing to check the statement against."""
        response = self.record(provider_ref="  ")

        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    def test_a_card_payment_cannot_be_marked_paid_by_hand(self):
        """This is the whole re-query-before-believing design. A hand-set card
        payment is a figure in the ledger no money ever matched."""
        card = a_payment(order=an_order(), method="card")

        response = self.record(card)

        self.assertEqual(response.status_code, 400)
        card.refresh_from_db()
        self.assertEqual(card.status, "pending")

    def test_an_mpesa_payment_cannot_either(self):
        mpesa = a_payment(order=an_order(), method="mpesa")

        self.assertEqual(self.record(mpesa).status_code, 400)

    def test_it_cannot_be_recorded_twice(self):
        """Two managers reading the same statement. The second must not
        overwrite the first one's name on the record."""
        self.assertEqual(self.record().status_code, 200)

        again = self.record(provider_ref="FT-SOMETHING-ELSE")

        self.assertEqual(again.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.provider_ref, "FT24081200123456")

    def test_sales_cannot_record_one(self):
        """Raising and chasing ask for money an agreed total says is owed.
        This asserts money arrived, with nothing behind it but the person."""
        self.as_sales()

        self.assertEqual(self.record().status_code, 403)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    def test_a_note_can_be_left_on_it(self):
        self.record(note="Equity, cleared 12 Aug")

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.note, "Equity, cleared 12 Aug")


class MpesaAmountTests(DjangoTestCase):
    """M-PESA moves whole shillings, and the rounding has to be the safe way.

    The callback never compares amounts - it re-queries the status and
    believes that - so an under-asked push is marked paid in full and the
    shortfall is invisible.
    """

    def test_a_whole_amount_is_unchanged(self):
        self.assertEqual(whole_shillings(Decimal("5000.00")), 5000)

    def test_a_fraction_rounds_up_rather_than_away(self):
        """int() truncated: 5,000.75 asked for 5,000 and settled the invoice."""
        self.assertEqual(whole_shillings(Decimal("5000.75")), 5001)
        self.assertEqual(whole_shillings(Decimal("5000.01")), 5001)

    def test_the_push_sends_the_rounded_figure(self):
        payment = a_payment(amount=Decimal("5000.75"), method="mpesa")

        with patch("payments.mpesa.get_mpesa_token", return_value="tok"), \
                patch("payments.mpesa.requests.post") as post:
            post.return_value.json.return_value = {"ResponseCode": "0"}
            start_mpesa_payment(payment, "254712345678")

        self.assertEqual(post.call_args.kwargs["json"]["Amount"], 5001)
