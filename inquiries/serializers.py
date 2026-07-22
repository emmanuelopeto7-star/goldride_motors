from rest_framework import serializers
from .models import Inquiry

class InquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquiry 
        fields = ["id", "car", "name", "phone", "message", "created_at"]