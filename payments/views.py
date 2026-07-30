from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.exceptions import ValidationError

from .models import Payment
from .services import (
    start_paystack_payment,
    verify_paystack_signature,
    verify_paystack_payment,
)


class InitiatePaymentView(APIView):
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
            payment = Payment.objects.get(reference=reference, status="pending")
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

