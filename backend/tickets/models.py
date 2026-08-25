from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TicketQuerySet(models.QuerySet):
    def unclaimed(self):
        return self.filter(status=Ticket.OPEN)

    def owned_by(self, user):
        return self.filter(claimed_by=user)

    def live(self):
        """Everything still needing somebody - the queue as staff see it."""
        return self.exclude(status=Ticket.CLOSED)

    def with_subjects(self):
        """One query for a page of tickets rather than four per row.

        Both subjects are pulled even though a given row only has one: the
        list mixes kinds, and a null FK costs nothing to join.
        """
        return self.select_related(
            "claimed_by",
            "purchase_request",
            "purchase_request__car",
            "purchase_request__customer",
            "import_request",
            "import_request__customer",
            "inquiry",
            "inquiry__car",
            "inquiry__customer",
        )


class Ticket(models.Model):
    """One piece of work, owned by one agent at a time.

    This replaces the Approvals and Sourcing queues rather than sitting on top
    of them: those screens were two separate lists with no notion of who was
    dealing with what, so two people could work the same purchase request and
    neither would know. A ticket is the ownership record that was missing.

    The subject is a real foreign key per kind, not a generic relation. Two
    columns is a migration's worth of work when a third kind arrives, and in
    exchange the database enforces that the row points at something that
    exists, and a page of tickets is one query instead of a contenttypes join
    per row.
    """

    APPROVAL = "approval"
    SOURCING = "sourcing"
    ENQUIRY = "enquiry"
    KIND_CHOICES = [
        (APPROVAL, "Purchase approval"),
        (SOURCING, "Import sourcing"),
        (ENQUIRY, "Enquiry"),
    ]

    OPEN = "open"
    CLAIMED = "claimed"
    CLOSED = "closed"
    STATUS_CHOICES = [
        (OPEN, "Open"),
        (CLAIMED, "Claimed"),
        (CLOSED, "Closed"),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)

    # OneToOne, not ForeignKey: a request raises exactly one ticket. Without
    # this a retried signal or a double POST quietly creates a second ticket
    # for the same work, which is the very thing tickets exist to prevent.
    purchase_request = models.OneToOneField(
        "purchases.PurchaseRequest",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ticket",
    )
    import_request = models.OneToOneField(
        "imports.ImportRequest",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ticket",
    )
    inquiry = models.OneToOneField(
        "inquiries.Inquiry",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ticket",
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TicketQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # The kind and the subject column must agree. Without this a row
            # can claim to be an approval while pointing at an import request,
            # and every reader that dispatches on kind then breaks.
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="approval",
                        purchase_request__isnull=False,
                        import_request__isnull=True,
                        inquiry__isnull=True,
                    )
                    | Q(
                        kind="sourcing",
                        import_request__isnull=False,
                        purchase_request__isnull=True,
                        inquiry__isnull=True,
                    )
                    | Q(
                        kind="enquiry",
                        inquiry__isnull=False,
                        purchase_request__isnull=True,
                        import_request__isnull=True,
                    )
                ),
                name="ticket_subject_matches_kind",
            ),
            # An open ticket is by definition nobody's. Letting the two drift
            # apart would make "open" mean two different things depending on
            # which column you read.
            models.CheckConstraint(
                condition=Q(status="open", claimed_by__isnull=True) | ~Q(status="open"),
                name="open_ticket_is_unclaimed",
            ),
        ]

    def __str__(self):
        return f"#{self.pk} {self.get_kind_display()}"

    @property
    def subject(self):
        """The request this ticket is about, whichever kind it is."""
        if self.kind == self.APPROVAL:
            return self.purchase_request
        if self.kind == self.ENQUIRY:
            return self.inquiry
        return self.import_request

    def claim(self, user):
        """Take ownership. True if this call took it, False if it was gone.

        The condition is part of the UPDATE, not a Python `if`. Two agents
        clicking at the same moment both read claimed_by as None, so a
        check-then-save hands the same ticket to both and each sees success.
        Here the database decides: the second UPDATE matches no rows and
        reports zero, which is the answer the caller needs.
        """
        taken = Ticket.objects.filter(
            pk=self.pk, status=self.OPEN, claimed_by__isnull=True
        ).update(claimed_by=user, claimed_at=timezone.now(), status=self.CLAIMED)

        if taken:
            self.refresh_from_db()
        return bool(taken)

    def release(self):
        """Hand it back to the queue - picked up by mistake, or going off shift."""
        released = Ticket.objects.filter(pk=self.pk, status=self.CLAIMED).update(
            claimed_by=None, claimed_at=None, status=self.OPEN
        )
        if released:
            self.refresh_from_db()
        return bool(released)

    def close(self):
        """Done. claimed_by is kept: it is the record of who dealt with it."""
        closed = Ticket.objects.filter(pk=self.pk).exclude(status=self.CLOSED).update(
            status=self.CLOSED, closed_at=timezone.now()
        )
        if closed:
            self.refresh_from_db()
        return bool(closed)
