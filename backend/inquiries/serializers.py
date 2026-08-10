from rest_framework import serializers
from .models import Inquiry


class InquirySerializer(serializers.ModelSerializer):
    car_display = serializers.StringRelatedField(source="car", read_only=True)

    class Meta:
        model = Inquiry
        fields = [
            "id",
            "car",
            "car_display",
            "name",
            "phone",
            "email",
            "message",
            "created_at",
        ]
        read_only_fields = ["email", "created_at"]
        extra_kwargs = {
            "name": {"required": False},
            "phone": {"required": True},
        }


class StaffInquirySerializer(InquirySerializer):
    customer_username = serializers.CharField(
        source="customer.username", read_only=True, default=None
    )

    class Meta(InquirySerializer.Meta):
        fields = InquirySerializer.Meta.fields + ["customer_username"]
