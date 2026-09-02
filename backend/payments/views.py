from rest_framework import generics
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.db import transaction
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from rest_framework.permissions import AllowAny

from goldride_app.permissions import IsCustomer

from .dispatch import dispatch_payment
from .audit import settle
from .models import Payment, PaymentEvent
from .mpesa import query_mpesa_payment
from .serializers import (
    CheckoutResponseSerializer,
    DispatchRequestSerializer,
    InitiatePaymentRequestSerializer,
    PaymentSerializer,
)
from .services import (
    start_paystack_payment,
    verify_paystack_payment,
    verify_paystack_signature,
)


class MyPaymentsView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsCustomer]

    def get_queryset(self):
        # This used to reconcile the caller's pending payments inline. It made
        # a customer's page load wait on Paystack and Safaricom - up to two
        # minutes per payment on the old timeout - and a hung provider held the
        # request thread open for all of it.
        #
        # Nothing is lost by removing it. The happy path is the webhook, which
        # is immediate; the backstop is the sweep, which now runs on its own
        # every RECONCILE_INTERVAL_MINUTES instead of only when somebody looks.
        return (
            Payment.objects.filter(order__customer=self.request.user)
            .order_by("-created_at")
        )


class MyPaymentDispatchView(APIView):
    permission_classes = [IsCustomer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payments"

    @extend_schema(
        request=DispatchRequestSerializer,
        responses={200: CheckoutResponseSerializer},
        description="Re-send collection for one of your own pending payments: "
                    "a Paystack checkout link, or an M-PESA prompt to your phone.",
    )
    def post(self, request, reference):
        payment = get_object_or_404(
            Payment,
            reference=reference,
            order__customer=request.user,
            status="pending",
        )

        phone = request.data.get("phone") or payment.order.phone
        ok, detail = dispatch_payment(payment, email=request.user.email, phone=phone)

        if not ok:
            return Response({"error": detail}, status=400)

        if payment.method == "card":
            return Response({"checkout_url": detail})
        return Response({"detail": "M-PESA prompt sent to your phone"})


class InitiatePaymentView(APIView):
    """A checkout link for one of your own pending invoices.

    This had no permission class at all, which in DRF means anyone at all.
    Worse, it took the receipt address from the request body: hand it a
    reference and your own email and Paystack sent you the checkout for
    somebody else's invoice. The amount was always read from the database, so
    the sum could not be tampered with - but who was being asked to pay, and
    where the receipt landed, could be.

    Both halves are closed here. The caller must be signed in, the invoice is
    looked up against their own orders, and the address is theirs rather than
    whatever was typed into the request.
    """

    permission_classes = [IsCustomer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payments"

    @extend_schema(
        request=InitiatePaymentRequestSerializer,
        responses={200: CheckoutResponseSerializer},
        description="Exchange one of your own payment references for a Paystack "
                    "checkout URL. The amount is read from the database, never "
                    "from the request, and the receipt goes to your account's "
                    "own email address.",
    )
    def post(self, request):
        reference = request.data.get("reference")
        if not reference:
            return Response({"error": "reference is required"}, status=400)

        try:
            payment = Payment.objects.get(
                reference=reference,
                status="pending",
                order__customer=request.user,
            )
        except (Payment.DoesNotExist, ValidationError, ValueError):
            # Same answer either way: a reference that is not yours must not be
            # distinguishable from one that does not exist.
            return Response({"error": "payment not found"}, status=404)

        url = start_paystack_payment(payment, request.user.email)
        if url is None:
            return Response({"error": "could not start payment"}, status=502)
        return Response({"checkout_url": url})


@extend_schema(exclude=True)
class PaystackWebhookView(APIView):
    def post(self, request):
        signature = request.headers.get("x-paystack-signature")
        if not verify_paystack_signature(request.body, signature):
            return Response({"error": "invalid signature"}, status=400)

        event = request.data.get("event")
        reference = request.data.get("data", {}).get("reference")

        if not event or not reference:
            return Response({"status": "ignored"})

        if event != "charge.success":
            return Response({"status": "ignored"})

        verified = verify_paystack_payment(reference)
        if verified is None:
            return Response({"status": "could not verify"})

        if verified.get("status") != "success":
            return Response({"status": "not successful"})

        try:
            payment = Payment.objects.get(
                paystack_ref=reference, status="pending"
            )
        except (Payment.DoesNotExist, ValidationError):
            return Response({"status": "no pending payment"})

        if verified.get("amount") != int(payment.amount * 100):
            payment.note = "amount mismatch"
            payment.save(update_fields=["note", "updated_at"])
            return Response({"status": "amount mismatch"})

        # settle() holds the lock and re-checks the status inside it, so the
        # race this used to guard against is still guarded - and the change is
        # now written into the payment's history rather than only onto the row.
        settle(
            payment,
            to_status="paid",
            source=PaymentEvent.WEBHOOK,
            detail=f"Paystack charge.success, verified as {reference}",
            provider_ref=str(verified.get("id")),
        )
        return Response({"status": "ok"})


@extend_schema(exclude=True)
class MpesaCallbackView(APIView):
    def post(self, request):
        stk = request.data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk.get("CheckoutRequestID")

        if not checkout_id:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        if not Payment.objects.filter(
            checkout_request_id=checkout_id, status="pending"
        ).exists():
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        result = query_mpesa_payment(checkout_id)
        if result is None or str(result.get("ResultCode")) != "0":
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        receipt = ""
        for item in stk.get("CallbackMetadata", {}).get("Item", []):
            if item.get("Name") == "MpesaReceiptNumber":
                receipt = item.get("Value", "")

        try:
            payment = Payment.objects.get(
                checkout_request_id=checkout_id, status="pending"
            )
        except Payment.DoesNotExist:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        settle(
            payment,
            to_status="paid",
            source=PaymentEvent.CALLBACK,
            detail=f"M-PESA receipt {receipt}" if receipt else "M-PESA callback",
            provider_ref=str(receipt),
        )
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class PayNowView(APIView):
    """Follow a payment link: mint a fresh checkout and forward to it.

    Deliberately open, and keyed on the reference alone - see the note in
    pay_link.py. It only ever forwards to the provider; it reveals nothing
    about the payment to whoever opens it, and settled or cancelled invoices
    land back on the site rather than at a checkout.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payments"

    @extend_schema(
        responses={302: None},
        description="Redirects to a freshly minted Paystack checkout for this "
                    "payment. Settled or unknown references are sent to the "
                    "site rather than told which they were.",
    )
    def get(self, request, reference):
        payment = Payment.objects.filter(
            reference=reference, status="pending", method="card"
        ).first()

        if payment is None:
            # Same answer for settled, cancelled and never-existed: whoever is
            # holding this link is not owed a report on somebody's invoice.
            return redirect(f"{settings.FRONTEND_URL}/?pay=unavailable")

        # The account first, then whatever address this checkout was last
        # minted against - an order raised for a walk-in has no account, and
        # their link has to keep working too. Never anything from the request:
        # whoever opens the link does not get to choose where a receipt lands.
        account = payment.order.customer
        email = (account.email if account else "") or payment.checkout_email

        ok, detail = dispatch_payment(payment, email=email or None)

        if not ok:
            return redirect(f"{settings.FRONTEND_URL}/?pay=unavailable")

        return redirect(detail)
