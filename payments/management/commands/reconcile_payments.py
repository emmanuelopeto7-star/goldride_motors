from django.core.management.base import BaseCommand

from payments.models import Payment
from payments.mpesa import query_mpesa_payment
from payments.services import verify_paystack_payment


class Command(BaseCommand):
    help = "Ask each provider what happened to every pending payment"

    def handle(self, *args, **options):
        pending = Payment.objects.filter(status="pending").order_by("created_at")
        self.stdout.write(f"checking {pending.count()} pending payments\n")

        for payment in pending:
            if payment.method == "card":
                self.check_card(payment)
            elif payment.method == "mpesa":
                self.check_mpesa(payment)
            else:
                self.report(payment, "manual - staff decides", changed=False)

    def check_card(self, payment):
        data = verify_paystack_payment(str(payment.reference))
        if data is None:
            return self.report(payment, "no transaction at Paystack", changed=False)

        state = data.get("status")
        if state == "success":
            payment.status = "paid"
            payment.provider_ref = str(data.get("id"))
            payment.save()
            return self.report(payment, "success", changed=True)

        if state in ("failed", "abandoned", "reversed"):
            payment.status = "failed"
            payment.note = state
            payment.save()
            return self.report(payment, state, changed=True)

        self.report(payment, f"still {state}", changed=False)

    def check_mpesa(self, payment):
        if not payment.checkout_request_id:
            return self.report(payment, "never pushed", changed=False)

        data = query_mpesa_payment(payment.checkout_request_id)
        if data is None:
            return self.report(payment, "query failed", changed=False)

        code = str(data.get("ResultCode"))
        desc = data.get("ResultDesc", "")

        if code == "0":
            payment.status = "paid"
            payment.save()
            return self.report(payment, "success", changed=True)

        if code in ("1", "1032", "1037", "2001"):
            payment.status = "failed"
            payment.note = desc[:200]
            payment.save()
            return self.report(payment, f"{code} {desc}", changed=True)

        self.report(payment, f"code {code} - still processing", changed=False)

    def report(self, payment, message, changed):
        line = f"{str(payment.reference)[:8]}  {payment.method:6}  {message}"
        if changed:
            self.stdout.write(self.style.SUCCESS(f"{line}  -> {payment.status}"))
        else:
            self.stdout.write(f"{line}  -> unchanged")