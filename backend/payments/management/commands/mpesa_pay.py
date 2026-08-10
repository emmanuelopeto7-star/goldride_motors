from django.core.management.base import BaseCommand

from payments.models import Payment
from payments.mpesa import start_mpesa_payment


class Command(BaseCommand):
    help = "Send an M-PESA STK push for an existing payment"

    def add_arguments(self, parser):
        parser.add_argument("reference")
        parser.add_argument("phone")

    def handle(self, *args, **options):
        payment = Payment.objects.get(reference=options["reference"])
        self.stdout.write(f"invoice: {payment.amount} KES - {payment.order}")

        result = start_mpesa_payment(payment, options["phone"])
        if result is None:
            self.stdout.write(self.style.ERROR("push failed"))
            return

        self.stdout.write(
            self.style.SUCCESS(f"push sent: {result.get('CheckoutRequestID')}")
        )