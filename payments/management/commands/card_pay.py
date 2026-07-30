from django.core.management.base import BaseCommand

from payments.models import Payment
from payments.services import start_paystack_payment


class Command(BaseCommand):
    help = "Start a Paystack checkout for an existing payment"

    def add_arguments(self, parser):
        parser.add_argument("reference")
        parser.add_argument("email")

    def handle(self, *args, **options):
        payment = Payment.objects.get(reference=options["reference"], status="pending")
        self.stdout.write(f"invoice: {payment.amount} KES - {payment.order}")

        url = start_paystack_payment(payment, options["email"])
        if url is None:
            self.stdout.write(
                self.style.ERROR("could not start payment - reference may already be used")
            )
            return

        self.stdout.write(self.style.SUCCESS(url))