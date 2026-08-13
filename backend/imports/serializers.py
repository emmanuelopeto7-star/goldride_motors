from rest_framework import serializers
from .models import ImportOrder, ImportMilestone

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
