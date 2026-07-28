from rest_framework import serializers
from .models import ImportOrder, ImportMilestone

class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
       model = ImportMilestone
       fields = ["stage", "note", "created_at"]

class TrackingSerializer(serializers.ModelSerializer):
    milestones = MilestoneSerializer(many=True, read_only=True)

    class Meta:
        model = ImportOrder
        fields = ["car_description", "current_stage", "milestones"]