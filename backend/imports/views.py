from rest_framework import generics
from rest_framework.throttling import ScopedRateThrottle

from goldride_app.permissions import IsCustomer

from .models import ImportOrder
from .serializers import CustomerOrderSerializer, TrackingSerializer


class TrackingView(generics.RetrieveAPIView):
    queryset = ImportOrder.objects.all()
    serializer_class = TrackingSerializer
    lookup_field = "token"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "tracking"


class MyOrdersView(generics.ListAPIView):
    serializer_class = CustomerOrderSerializer
    permission_classes = [IsCustomer]

    def get_queryset(self):
        return ImportOrder.objects.filter(
            customer=self.request.user
        ).order_by("-created_at")
