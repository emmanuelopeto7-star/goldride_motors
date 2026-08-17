from rest_framework import serializers
from .models import ImportMilestone, ImportOrder, ImportRequest, SourcedUnit


def money(**kwargs):
    return serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True, **kwargs
    )


class SourcedUnitSerializer(serializers.ModelSerializer):
    """What the customer sees when choosing.

    Every KRA charge is itemised, because a customer comparing importers is
    really comparing tax arithmetic, and a single "duties" figure is the one
    line they cannot check. What stays hidden is the purchase price in Japan
    and the landed cost: a quote is a price, not an invitation to audit the
    margin. Staff get those through StaffSourcedUnitSerializer.
    """

    cnf_kes = money()
    taxes_kes = money()
    import_duty_kes = money()
    excise_duty_kes = money()
    vat_kes = money()
    idf_kes = money()
    rdl_kes = money()
    clearing_kes = money()
    service_fee_kes = money()
    total_kes = money()

    class Meta:
        model = SourcedUnit
        fields = [
            "id", "make", "model", "year", "mileage_km", "grade",
            "exterior_colour", "chassis_number", "auction_sheet_url", "photo",
            "dollar_rate",
            "cnf_kes",
            "import_duty_kes", "excise_duty_kes", "vat_kes", "idf_kes",
            "rdl_kes", "taxes_kes",
            "clearing_kes", "service_fee_kes", "total_kes",
            "status", "rejected_reason", "created_at",
        ]
        read_only_fields = fields


class ImportRequestSerializer(serializers.ModelSerializer):
    """Raising a request. Open to guests, so the contact fields are required
    here rather than read off an account that may not exist."""

    units = SourcedUnitSerializer(many=True, read_only=True)

    class Meta:
        model = ImportRequest
        fields = [
            "id", "contact_name", "email", "phone",
            "make", "model", "year", "budget_kes", "notes",
            "status", "token", "created_at", "units",
        ]
        read_only_fields = ["id", "status", "token", "created_at", "units"]

class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
       model = ImportMilestone
       fields = ["stage", "note", "created_at"]

class TrackingSerializer(serializers.ModelSerializer):
    milestones = MilestoneSerializer(many=True, read_only=True)
    is_cancelled = serializers.BooleanField(read_only=True)

    class Meta:
        model = ImportOrder
        # cancel_reason is deliberately absent: this page is public to anyone
        # holding the link, and the reason can be personal.
        fields = [
            "car_description",
            "current_stage",
            "is_cancelled",
            "cancelled_at",
            "milestones",
        ]


class CustomerOrderSerializer(serializers.ModelSerializer):
    milestones = MilestoneSerializer(many=True, read_only=True)
    amount_paid = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    is_settled = serializers.BooleanField(read_only=True)
    is_cancelled = serializers.BooleanField(read_only=True)

    class Meta:
        model = ImportOrder
        fields = [
            "id",
            "car_description",
            "current_stage",
            "total_amount",
            "amount_paid",
            "balance",
            "is_settled",
            "is_cancelled",
            "cancelled_at",
            "cancel_reason",
            "token",
            "created_at",
            "milestones",
        ]
        read_only_fields = fields
