from rest_framework import serializers

from cars.models import Car, CarImage
from imports.models import ImportMilestone, ImportOrder
from payments.models import Payment


class StaffCarSerializer(serializers.ModelSerializer):
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
        ]


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
            "token",
            "created_at",
            "milestones",
        ]
        read_only_fields = ["token", "created_at"]

    def validate_car(self, car):
        if car is None:
            return car

        if car.availability == "sold":
            raise serializers.ValidationError("This car has already been sold.")

        clash = ImportOrder.objects.filter(car=car)
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
