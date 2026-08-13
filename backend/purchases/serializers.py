from rest_framework import serializers

from .models import PurchaseRequest


class PurchaseRequestSerializer(serializers.ModelSerializer):
    car_display = serializers.StringRelatedField(source="car", read_only=True)
    price = serializers.DecimalField(
        source="car.price", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = PurchaseRequest
        fields = [
            "id",
            "car",
            "car_display",
            "price",
            "preferred_method",
            "phone",
            "message",
            "status",
            "decision_note",
            "created_at",
            "reviewed_at",
            "order",
        ]
        read_only_fields = [
            "status",
            "decision_note",
            "created_at",
            "reviewed_at",
            "order",
        ]

    def validate_car(self, car):
        if car.availability == "sold":
            raise serializers.ValidationError("This car has already been sold.")
        return car


class StaffPurchaseRequestSerializer(PurchaseRequestSerializer):
    customer_username = serializers.CharField(
        source="customer.username", read_only=True
    )
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    reviewed_by_username = serializers.CharField(
        source="reviewed_by.username", read_only=True, default=None
    )
    car_title = serializers.SerializerMethodField()

    class Meta(PurchaseRequestSerializer.Meta):
        fields = PurchaseRequestSerializer.Meta.fields + [
            "car_title",
            "customer_username",
            "customer_email",
            "reviewed_by_username",
        ]

    def get_car_title(self, purchase_request):
        """`car_display` is Car.__str__, which trails the entire description
        and prices in dollars. Unusable as a heading, so the queue gets the
        same "2019 Toyota Prado" form the storefront uses."""
        car = purchase_request.car
        return f"{car.year} {car.make} {car.model}"


class DecisionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)


class ApprovalResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    order = serializers.IntegerField(required=False)
    payment_reference = serializers.UUIDField(required=False)
    method = serializers.CharField(required=False)
    amount = serializers.CharField(required=False)
    dispatched = serializers.BooleanField(required=False)
    checkout_url = serializers.URLField(required=False)
    detail = serializers.CharField(required=False)
