from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from goldride_app.permissions import IsCustomer

from .models import ImportOrder, ImportRequest, SourcedUnit
from .serializers import (
    CustomerOrderSerializer,
    ImportRequestSerializer,
    TrackingSerializer,
)
from .services import notify_cancelled, notify_new_request


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


class ImportRequestCreateView(generics.CreateAPIView):
    """Raise an import request. Deliberately public.

    Someone who wants a car found is a lead, and putting a registration wall
    in front of a lead loses it. The token in the response is how an
    unregistered customer gets back to the request afterwards.
    """

    serializer_class = ImportRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "imports"

    def perform_create(self, serializer):
        # Attach the account when there is one, so it also shows up under
        # /api/my/ - but never require it.
        user = self.request.user
        request_obj = serializer.save(
            customer=user if user.is_authenticated else None
        )
        notify_new_request(request_obj)


class ImportRequestTrackingView(generics.RetrieveAPIView):
    """The customer's view of their request and whatever we have sourced.

    Public, like order tracking: the UUID is the credential. That is why the
    serializer withholds the purchase price and shows only the quote.
    """

    queryset = ImportRequest.objects.prefetch_related("units")
    serializer_class = ImportRequestSerializer
    lookup_field = "token"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "tracking"


class SourcedUnitDecisionView(APIView):
    """The customer choosing, or declining, a unit we found.

    Reached with the request token rather than a login, for the same reason
    the request could be raised without one.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "tracking"

    @extend_schema(
        request=inline_serializer('UnitDecision', {
            'decision': serializers.ChoiceField(choices=["select", "reject"]),
            'reason': serializers.CharField(required=False),
        }),
        responses={200: ImportRequestSerializer},
        description="Select or reject a sourced unit. Selecting one rejects "
                    "the rest - choosing is also declining.",
    )
    def post(self, request, token, pk):
        try:
            unit = SourcedUnit.objects.get(pk=pk, request__token=token)
        except SourcedUnit.DoesNotExist:
            return Response({"error": "not found"}, status=404)

        decision = request.data.get("decision")
        if decision == "select":
            ok, detail = unit.select()
        elif decision == "reject":
            ok, detail = unit.reject(request.data.get("reason", ""))
        else:
            return Response(
                {"decision": 'Must be "select" or "reject".'}, status=400
            )

        if not ok:
            return Response({"error": detail}, status=400)

        unit.request.refresh_from_db()
        return Response(ImportRequestSerializer(unit.request).data)
