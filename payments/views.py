from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .services import start_paystack_payment


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
