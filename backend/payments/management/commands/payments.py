from django.core.management.base import BaseCommand

from payments.models import Payment


class Command(BaseCommand):
    help = "List all payments"

    def handle(self, *args, **options):
        for p in Payment.objects.order_by("created_at"):
            self.stdout.write(
                f"{p.reference}  {p.amount:>12}  {p.method:6}  "
                f"{p.status:8}  {p.provider_ref or '-'}"
            )