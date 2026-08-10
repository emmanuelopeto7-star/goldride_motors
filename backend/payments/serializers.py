from rest_framework import serializers

from .models import Payment


class InitiatePaymentRequestSerializer(serializers.Serializer):
    reference = serializers.UUIDField(help_text="The payment reference given to the customer.")
    email = serializers.EmailField()


class DispatchRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(
        required=False, allow_blank=True,
        help_text="M-PESA number as 2547XXXXXXXX. Defaults to the order's phone.",
    )
    email = serializers.EmailField(required=False, allow_blank=True)


class CheckoutResponseSerializer(serializers.Serializer):
    checkout_url = serializers.URLField(required=False)
    detail = serializers.CharField(required=False)


class PaymentSerializer(serializers.ModelSerializer):
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
        read_only_fields = fields
