from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import filters, generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from cars.models import Car, CarImage
from imports.models import ImportMilestone, ImportOrder
from payments.dispatch import dispatch_payment
from payments.serializers import CheckoutResponseSerializer, DispatchRequestSerializer
from payments.models import Payment
from payments.reconciliation import reconcile_payment, reconcile_pending

from .permissions import IsManager, IsSales
from .staff_serializers import (
    StaffCarImageSerializer,
    StaffCarSerializer,
    StaffMilestoneSerializer,
    StaffOrderSerializer,
    StaffPaymentSerializer,
)


class ManagerToDelete:
    """Sales may read and edit; only a Manager may delete."""

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsManager()]
        return [IsSales()]


# --- cars ------------------------------------------------------------------

class StaffCarListView(generics.ListCreateAPIView):
    queryset = Car.objects.all().order_by("-id")
    serializer_class = StaffCarSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["make", "model", "year", "condition", "availability"]
    # Chassis search matters most to whoever is checking a unit is not already
    # on the lot, so it has to reach the staff list and not just the admin.
    search_fields = ["make", "model", "description", "vin", "reference"]


class StaffCarDetailView(ManagerToDelete, generics.RetrieveUpdateDestroyAPIView):
    queryset = Car.objects.all()
    serializer_class = StaffCarSerializer


class StaffCarImageView(generics.ListCreateAPIView):
    queryset = CarImage.objects.all().order_by("-id")
    serializer_class = StaffCarImageSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["car"]


class StaffCarImageDetailView(ManagerToDelete, generics.RetrieveDestroyAPIView):
    queryset = CarImage.objects.all()
    serializer_class = StaffCarImageSerializer


# --- import orders ---------------------------------------------------------

class StaffOrderListView(generics.ListCreateAPIView):
    queryset = ImportOrder.objects.all().order_by("-created_at")
    serializer_class = StaffOrderSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["current_stage"]
    search_fields = ["customer_name", "phone", "car_description"]


class StaffOrderDetailView(ManagerToDelete, generics.RetrieveUpdateDestroyAPIView):
    queryset = ImportOrder.objects.all()
    serializer_class = StaffOrderSerializer


class StaffMilestoneView(generics.ListCreateAPIView):
    queryset = ImportMilestone.objects.all().order_by("-created_at")
    serializer_class = StaffMilestoneSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["order", "stage"]

    def perform_create(self, serializer):
        milestone = serializer.save()
        # Keep the headline stage in step with the latest milestone, so the
        # customer's tracking page can never contradict its own history.
        order = milestone.order
        if order.current_stage != milestone.stage:
            order.current_stage = milestone.stage
            order.save()


# --- payments --------------------------------------------------------------

class StaffPaymentListView(generics.ListCreateAPIView):
    queryset = Payment.objects.all().order_by("-created_at")
    serializer_class = StaffPaymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "method", "order"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsManager()]
        return [IsSales()]


class StaffPaymentDispatchView(APIView):
    permission_classes = [IsManager]

    @extend_schema(
        request=DispatchRequestSerializer,
        responses={200: CheckoutResponseSerializer},
        description="Manager only. Send a checkout link or an M-PESA prompt for a pending payment.",
    )
    def post(self, request, reference):
        try:
            payment = Payment.objects.get(reference=reference, status="pending")
        except Payment.DoesNotExist:
            return Response({"error": "no pending payment with that reference"}, status=404)

        order = payment.order
        email = request.data.get("email") or (
            order.customer.email if order.customer else ""
        )
        phone = request.data.get("phone") or order.phone

        ok, detail = dispatch_payment(payment, email=email, phone=phone)
        if not ok:
            return Response({"error": detail}, status=400)

        if payment.method == "card":
            return Response({"checkout_url": detail})
        return Response({"detail": f"M-PESA prompt sent to {phone}"})


class StaffReconcileAllView(APIView):
    permission_classes = [IsSales]

    @extend_schema(
        operation_id='staff_payments_reconcile_all',
        request=None,
        responses={200: inline_serializer('Reconcile', {
            'checked': serializers.IntegerField(required=False),
            'updated': serializers.IntegerField(required=False),
            'reference': serializers.UUIDField(required=False),
            'changed': serializers.BooleanField(required=False),
            'detail': serializers.CharField(required=False),
            'status': serializers.CharField(required=False),
        })},
        description="Ask the provider what happened to pending payments. "
                    "With a reference, checks one; without, checks all.",
    )
    def post(self, request):
        results = reconcile_pending()
        return Response({
            "checked": len(results),
            "updated": sum(1 for _, changed, _ in results if changed),
            "results": [
                {"reference": str(p.reference), "changed": c, "detail": m, "status": p.status}
                for p, c, m in results
            ],
        })


class StaffReconcileOneView(APIView):
    permission_classes = [IsSales]

    @extend_schema(
        operation_id='staff_payments_reconcile_one',
        request=None,
        responses={200: inline_serializer('ReconcileOne', {
            'reference': serializers.UUIDField(),
            'changed': serializers.BooleanField(),
            'detail': serializers.CharField(),
            'status': serializers.CharField(),
        })},
        description="Ask the provider what happened to one payment.",
    )
    def post(self, request, reference):
        try:
            payment = Payment.objects.get(reference=reference)
        except Payment.DoesNotExist:
            return Response({"error": "not found"}, status=404)

        changed, message = reconcile_payment(payment)
        return Response({
            "reference": str(payment.reference),
            "changed": changed,
            "detail": message,
            "status": payment.status,
        })
