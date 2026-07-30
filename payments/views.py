from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from django.core.exceptions import ValidationError

from .models import Payment
from .mpesa import query_mpesa_payment
from .services import (
    start_paystack_payment,
    verify_paystack_payment,
    verify_paystack_signature,
)


class InitiatePaymentView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payments"

    def post(self, request):
        reference=request.data.get("reference")
        email=request.data.get("email")
        if not reference or not email:
            return Response({"error": "reference and email are required"}, status=400)
        try:
            payment = Payment.objects.get(reference=reference, status="pending")
        except Payment.DoesNotExist:
            return Response({"error": "payment not found"}, status=404)
        url = start_paystack_payment(payment, email)
        if url is None:
            return Response({"error": "could not start payment"}, status=502)
        return Response({"checkout_url": url})


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
            payment = Payment.objects.get(paystack_ref=reference, status="pending")
        except (Payment.DoesNotExist, ValidationError):
            return Response({"status": "no pending payment"})

        if verified.get("amount") != int(payment.amount * 100):
            payment.note = "amount mismatch"
            payment.save()
            return Response({"status": "amount mismatch"})

        payment.status = "paid"
        payment.provider_ref = str(verified.get("id"))
        payment.save()
        return Response({"status": "ok"})


class MpesaCallbackView(APIView):
    def post(self, request):
        stk = request.data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk.get("CheckoutRequestID")

        if not checkout_id:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        try:
            payment = Payment.objects.get(
                checkout_request_id=checkout_id, status="pending"
            )
        except Payment.DoesNotExist:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        result = query_mpesa_payment(checkout_id)
        if result is None or str(result.get("ResultCode")) != "0":
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        receipt = ""
        for item in stk.get("CallbackMetadata", {}).get("Item", []):
            if item.get("Name") == "MpesaReceiptNumber":
                receipt = item.get("Value", "")

        payment.status = "paid"
        payment.provider_ref = str(receipt)
        payment.save()
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})
