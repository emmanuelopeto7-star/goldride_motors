from rest_framework import generics
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from goldride_app.permissions import IsCustomer

from .dispatch import dispatch_payment
from .models import Payment
from .mpesa import query_mpesa_payment
from .reconciliation import reconcile_pending
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
        mine = Payment.objects.filter(order__customer=self.request.user)
        reconcile_pending(mine.filter(status="pending"))
        return mine.order_by("-created_at")


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
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(
                    paystack_ref=reference, status="pending"
                )

                if verified.get("amount") != int(payment.amount * 100):
                    payment.note = "amount mismatch"
                    payment.save()
                    return Response({"status": "amount mismatch"})

                payment.status = "paid"
                payment.provider_ref = str(verified.get("id"))
                payment.save()
        except (Payment.DoesNotExist, ValidationError):
            return Response({"status": "no pending payment"})

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
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(
                    checkout_request_id=checkout_id, status="pending"
                )
                payment.status = "paid"
                payment.provider_ref = str(receipt)
                payment.save()
        except Payment.DoesNotExist:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})
