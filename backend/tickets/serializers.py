from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    """One row of the queue, whatever kind of work it is.

    The summary fields are flattened deliberately. A ticket list mixing
    approvals and sourcing requests would otherwise force the frontend to
    branch on kind just to find a heading, and every new kind would mean
    another branch in the table. Dispatching happens here, once; the detail
    screen still reads the underlying request for anything specific.
    """

    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    claimed_by_username = serializers.CharField(
        source="claimed_by.username", read_only=True, default=None
    )
    subject_id = serializers.SerializerMethodField()
    # Whether there is an account behind this ticket. A guest may raise an
    # import request - contact details, no login - and there is nowhere to
    # deliver a chat message to one, so the screen offers the phone instead.
    has_customer = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "kind",
            "kind_label",
            "status",
            "status_label",
            "claimed_by",
            "claimed_by_username",
            "claimed_at",
            "closed_at",
            "created_at",
            "subject_id",
            "has_customer",
            "title",
            "customer",
            "amount",
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_has_customer(self, ticket):
        return ticket.customer is not None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_subject_id(self, ticket):
        """The id of the request itself - what the detail screen fetches."""
        subject = ticket.subject
        return subject.pk if subject else None

    @extend_schema_field(serializers.CharField())
    def get_title(self, ticket):
        subject = ticket.subject
        if subject is None:
            return ""
        if ticket.kind in (Ticket.APPROVAL, Ticket.ENQUIRY):
            # Both hang off a car we already list.
            car = subject.car
            return f"{car.year} {car.make} {car.model}"
        if ticket.kind == Ticket.DEALER:
            # A dealership's trading name, or a private seller's own name.
            return subject.display_name
        return f"{subject.year} {subject.make} {subject.model}"

    @extend_schema_field(serializers.CharField())
    def get_customer(self, ticket):
        subject = ticket.subject
        if subject is None:
            return ""
        if ticket.kind == Ticket.APPROVAL:
            return subject.customer.get_full_name() or subject.customer.username
        if ticket.kind == Ticket.ENQUIRY:
            # The name typed into the form. An enquiry can be made by someone
            # whose account name says nothing useful.
            return subject.name
        if ticket.kind == Ticket.DEALER:
            return subject.contact_name
        # A sourcing request may come from a guest, so the name is on the row
        # rather than on a user.
        return subject.contact_name

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True))
    def get_amount(self, ticket):
        """The listed price for an approval, the stated budget for a sourcing
        request. Different things, but the same column to an agent triaging."""
        subject = ticket.subject
        if subject is None:
            return None
        if ticket.kind in (Ticket.APPROVAL, Ticket.ENQUIRY):
            # The price lives on the car; the request only points at it.
            return subject.car.price
        if ticket.kind == Ticket.DEALER:
            # No amount is on the table yet - a dealership is asking to
            # start, not offering a figure.
            return None
        return subject.budget_kes
