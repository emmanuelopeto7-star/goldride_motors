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
    # Who answered, and what they said. The point of showing it: an agent
    # opening an answered enquiry should see the reply rather than an empty
    # box inviting them to send a second one.
    replied_by_username = serializers.CharField(
        source="replied_by.username", read_only=True, default=None
    )

    class Meta(InquirySerializer.Meta):
        fields = InquirySerializer.Meta.fields + [
            "customer_username",
            "reply",
            "replied_by_username",
            "replied_at",
            "reply_emailed",
        ]
        read_only_fields = InquirySerializer.Meta.read_only_fields + [
            "reply",
            "replied_at",
            "reply_emailed",
        ]
