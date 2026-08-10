from django.core.management.base import BaseCommand

from payments.models import Payment
from payments.reconciliation import reconcile_pending


class Command(BaseCommand):
    help = "Ask each provider what happened to every pending payment"

    def handle(self, *args, **options):
        pending = Payment.objects.filter(status="pending")
        self.stdout.write(f"checking {pending.count()} pending payments\n")

        changed = 0
        for payment, was_changed, message in reconcile_pending(pending):
            line = f"{str(payment.reference)[:8]}  {payment.method:6}  {message}"
            if was_changed:
                changed += 1
                self.stdout.write(
                    self.style.SUCCESS(f"{line}  -> {payment.status}")
                )
            else:
                self.stdout.write(f"{line}  -> unchanged")

        self.stdout.write(f"\n{changed} updated")
