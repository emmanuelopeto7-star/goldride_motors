from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from goldride_app.permissions import IsCustomer

from .models import ImportOrder
from .serializers import CustomerOrderSerializer, TrackingSerializer
from .services import notify_cancelled


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


class CancelOrderView(APIView):
    """A customer pulling out of their own import.

    Scoped to their own orders by the queryset, not by a permission check on
    the object - an id belonging to someone else has to 404, not 403, or the
    endpoint becomes a way to discover which order ids exist.
    """

    permission_classes = [IsCustomer]

    @extend_schema(
        request=inline_serializer('CancelOrder', {
            'reason': serializers.CharField(required=False),
        }),
        responses={200: CustomerOrderSerializer},
        description="Cancel your own import order and release the car.",
    )
    def post(self, request, pk):
        try:
            order = ImportOrder.objects.get(pk=pk, customer=request.user)
        except ImportOrder.DoesNotExist:
            return Response({"error": "not found"}, status=404)

        ok, detail = order.cancel(reason=request.data.get("reason", ""))
        if not ok:
            return Response({"error": detail}, status=400)

        notify_cancelled(order)
        return Response(CustomerOrderSerializer(order).data)
