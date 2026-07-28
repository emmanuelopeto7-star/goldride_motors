from django.shortcuts import render
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import generics

from .models import ImportOrder
from .serializers import TrackingSerializer

class TrackingView(generics.RetrieveAPIView):
    queryset = ImportOrder.objects.all()
    serializer_class = TrackingSerializer
    lookup_field = "token"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "tracking"

