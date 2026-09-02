from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid
from imports.models import ImportOrder

class Payment(models.Model):
    METHOD_CHOICES = [
        ("mpesa", "M-Pesa"),
        ("card", "Card"),
        ("manual", "Manual / Bank"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey(ImportOrder, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    provider_ref = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    paystack_ref = models.CharField(max_length=100, blank=True)
    checkout_url = models.URLField(max_length=300, blank=True)
    # The address the last checkout was minted against. Recorded because a
    # pay link has to mint another one later and Paystack requires an email:
    # an order raised for a walk-in has no account to read it off, so without
    # this their link would refuse forever.
    checkout_email = models.EmailField(blank=True)
    # Set whenever a checkout URL is stored. See CHECKOUT_LINK_MINUTES.
    checkout_expires_at = models.DateTimeField(null=True, blank=True)
    # When the customer was told how to pay. Blank means they have not been,
    # which is the difference between "waiting on them" and "waiting on us".
    checkout_sent_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)

    # A bank transfer has no provider to ask. Every other payment is believed
    # only after re-querying Paystack or Safaricom; this one is believed
    # because a person read a bank statement and said so - so who said it, and
    # when, is the only evidence there is. Null for anything the rails
    # confirmed themselves.
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )
    recorded_at = models.DateTimeField(null=True, blank=True)

    # When this became paid, stamped once and never moved again.
    #
    # `updated_at` cannot answer it: auto_now moves whenever anything on the
    # row changes, and reconciliation re-reads old payments by design. Group
    # revenue by updated_at and a reconcile run in September silently drags an
    # August payment into September - the chart rewrites its own history every
    # time the job runs. `created_at` is when the invoice was raised, which is
    # a different date and often a different month.
    paid_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def checkout_is_live(self):
        """Whether we are still offering this checkout link.

        Ours rather than Paystack's. Their URL keeps working at their end -
        initialize takes no expiry - so this decides only whether the app
        still shows it. Somebody who kept the raw link could still pay
        through it, and that is fine: they have paid, and the webhook checks
        with Paystack before believing anything.
        """
        if not self.checkout_url:
            return False
        if self.checkout_expires_at is None:
            # Raised before links had a lifetime. Treat it as still good
            # rather than retiring every old invoice on deploy.
            return True
        return timezone.now() < self.checkout_expires_at

    def save(self, *args, **kwargs):
        """Stamp `paid_at` the first time this row is paid.

        Here rather than at the four places that mark a payment paid - the
        webhook, the M-PESA callback, reconciliation and the record-by-hand
        view - because a fifth one will be written eventually and it will
        forget. The condition is `is None`, so re-saving a paid payment for
        any other reason cannot move the date.

        `update_fields` has to be extended as well: every caller that passes it
        lists the columns it knows about, and a column set here would otherwise
        be dropped on the way to the database.
        """
        if self.status == "paid" and self.paid_at is None:
            self.paid_at = timezone.now()
            fields = kwargs.get("update_fields")
            if fields is not None:
                kwargs["update_fields"] = list(fields) + ["paid_at"]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.amount} KES - {self.get_status_display()} - {self.order}"


class PaymentEvent(models.Model):
    """Every change of status a payment has ever had, and who caused it.

    Money records are the one place in this system where "what does the row say
    now" is not enough. A payment that reads `failed` cannot tell you whether
    Paystack said so, whether the nightly sweep decided it, or whether somebody
    here corrected it by hand at four in the afternoon - and those are three
    very different conversations to have with a customer.

    Append-only by construction: there is no update path and no delete, in the
    same spirit as PROTECT on Payment.order. A correction adds a row saying the
    status changed; it never rewrites the row that said otherwise.
    """

    WEBHOOK = "webhook"
    CALLBACK = "callback"
    RECONCILE = "reconcile"
    RECORDED = "recorded"
    CORRECTION = "correction"
    SOURCE_CHOICES = [
        (WEBHOOK, "Paystack webhook"),
        (CALLBACK, "M-PESA callback"),
        (RECONCILE, "Reconciliation"),
        (RECORDED, "Recorded by staff"),
        (CORRECTION, "Corrected by staff"),
    ]

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="events"
    )
    # Both ends kept: "pending -> paid" and "paid -> refunded" are different
    # facts, and storing only the destination loses the second one.
    from_status = models.CharField(max_length=10, choices=Payment.STATUS_CHOICES)
    to_status = models.CharField(max_length=10, choices=Payment.STATUS_CHOICES)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES)

    # Why. Free text because the useful reason is different every time: a
    # Safaricom ResultDesc, an amount mismatch, or a sentence a manager typed.
    detail = models.CharField(max_length=300, blank=True)

    # Null for anything the rails decided on their own. A row with an actor is
    # a row a person is answerable for.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["payment", "created_at"])]

    def __str__(self):
        return f"{self.payment_id}: {self.from_status} -> {self.to_status}"


class ReconciliationRun(models.Model):
    """One sweep of the pending payments: when, how long, what it found.

    Two jobs. It is the record staff read to know the sweep is alive - "last
    checked 6 minutes ago" is the difference between trusting the payments
    screen and not - and it is the lock the sweep claims, so that four web
    workers all running the same background thread produce one sweep between
    them rather than four hammering Paystack in parallel.
    """

    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    STATE_CHOICES = [
        (RUNNING, "Running"),
        (DONE, "Done"),
        (FAILED, "Failed"),
    ]

    AUTOMATIC = "automatic"
    COMMAND = "command"
    STAFF = "staff"
    TRIGGER_CHOICES = [
        (AUTOMATIC, "Scheduled sweep"),
        (COMMAND, "Management command"),
        (STAFF, "Asked for by staff"),
    ]

    state = models.CharField(max_length=8, choices=STATE_CHOICES, default=RUNNING)
    trigger = models.CharField(max_length=10, choices=TRIGGER_CHOICES)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    checked = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    # Whatever went wrong, if anything did. A sweep that cannot reach Paystack
    # must leave a mark, or "nothing changed" and "nothing was asked" look the
    # same on the screen.
    error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.get_trigger_display()} {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def seconds(self):
        if self.finished_at is None:
            return None
        return round((self.finished_at - self.started_at).total_seconds(), 1)
