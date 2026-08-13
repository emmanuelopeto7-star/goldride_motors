from rest_framework import serializers

from cars.models import Car, CarImage
from imports.models import ImportMilestone, ImportOrder
from payments.models import Payment


class StaffCarSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Car
        fields = [
            "id",
            "make",
            "model",
            "year",
            "price",
            "condition",
            "availability",
            "description",
            "image",
            "vin",
            "reference",
            "expires_at",
            "is_expired",
            "video_url",
        ]

    def validate_vin(self, vin):
        """DRF skips conditional UniqueConstraints when it builds validators, so
        without this the clash surfaces as a 500 from the database instead of a
        400 naming the field."""
        if not vin:
            return vin

        vin = vin.strip().upper()
        clash = Car.objects.filter(vin=vin)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "Another listing already uses this VIN / chassis number."
            )
        return vin


class StaffCarImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarImage
        fields = ["id", "car", "image"]


class StaffMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportMilestone
        fields = ["id", "order", "stage", "note", "created_at"]
        read_only_fields = ["created_at"]


class StaffOrderSerializer(serializers.ModelSerializer):
    amount_paid = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_settled = serializers.BooleanField(read_only=True)
    is_cancelled = serializers.BooleanField(read_only=True)
    milestones = StaffMilestoneSerializer(many=True, read_only=True)

    class Meta:
        model = ImportOrder
        fields = [
            "id",
            "customer",
            "customer_name",
            "phone",
            "car",
            "car_description",
            "current_stage",
            "total_amount",
            "amount_paid",
            "balance",
            "is_settled",
            "is_cancelled",
            "cancelled_at",
            "cancel_reason",
            "reactivated_at",
            "token",
            "created_at",
            "milestones",
        ]
        # Cancelling and reactivating go through their own endpoints so the
        # car's availability is always moved with them.
        read_only_fields = [
            "token", "created_at", "cancelled_at", "reactivated_at",
        ]

    def validate_car(self, car):
        if car is None:
            return car

        if car.availability == "sold":
            raise serializers.ValidationError("This car has already been sold.")

        # Matches ImportOrder.clean(): a cancelled order released its car, so it
        # no longer blocks a new one.
        clash = ImportOrder.objects.filter(car=car, cancelled_at__isnull=True)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "This car already has an import order against it."
            )
        return car


class StaffPaymentSerializer(serializers.ModelSerializer):
    order_display = serializers.StringRelatedField(source="order", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "reference",
            "order",
            "order_display",
            "amount",
            "method",
            "status",
            "provider_ref",
            "checkout_url",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "reference",
            "provider_ref",
            "checkout_url",
            "created_at",
            "updated_at",
        ]
