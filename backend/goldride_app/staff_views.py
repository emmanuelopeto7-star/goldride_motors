from decimal import Decimal

from django.conf import settings

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import filters, generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from cars.models import Car, CarImage
from imports.models import (
    ImportMilestone,
    ImportOrder,
    ImportRates,
    ImportRequest,
    SourcedUnit,
)
from imports.services import notify_units_sourced, send_reengagement
from payments.dispatch import dispatch_payment
from payments.notifications import send_payment_instructions
from payments.serializers import CheckoutResponseSerializer, DispatchRequestSerializer
from payments.models import Payment
from payments.reconciliation import reconcile_payment, reconcile_pending

from .permissions import IsManager, IsSales
from .staff_serializers import (
    StaffCarImageSerializer,
    StaffCarSerializer,
    StaffImportRequestSerializer,
    StaffMilestoneSerializer,
    StaffOrderSerializer,
    StaffPaymentSerializer,
    StaffSourcedUnitSerializer,
)


class ManagerToDelete:
    """Sales may read and edit; only a Manager may delete."""

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsManager()]
        return [IsSales()]


# --- cars ------------------------------------------------------------------

class StaffCarListView(generics.ListCreateAPIView):
    # Deliberately not .live() - staff are the only people who can renew a
    # lapsed listing, so they are the only people who must still see it.
    queryset = Car.objects.prefetch_related("images").order_by("-id")
    serializer_class = StaffCarSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["make", "model", "year", "condition", "availability"]
    # Chassis search matters most to whoever is checking a unit is not already
    # on the lot, so it has to reach the staff list and not just the admin.
    search_fields = ["make", "model", "description", "vin", "reference"]

    def get_queryset(self):
        queryset = super().get_queryset()
        # ?expired=true is the renewal worklist; the expression is a date
        # comparison rather than a column, so it cannot be a filterset field.
        expired = self.request.query_params.get("expired")
        if expired in ("true", "1"):
            queryset = queryset.exclude(pk__in=Car.objects.live().values("pk"))
        elif expired in ("false", "0"):
            queryset = queryset.filter(pk__in=Car.objects.live().values("pk"))

        # ?photos=none is the worklist for the catalogue's biggest gap.
        photos = self.request.query_params.get("photos")
        if photos == "none":
            queryset = queryset.filter(images__isnull=True, image="")
        elif photos == "some":
            queryset = queryset.exclude(images__isnull=True, image="")
        return queryset


class StaffCarDetailView(ManagerToDelete, generics.RetrieveUpdateDestroyAPIView):
    queryset = Car.objects.all()
    serializer_class = StaffCarSerializer


class StaffCarExtendView(APIView):
    """Renew a listing that is about to lapse, or has already.

    Sales rather than Manager: confirming a car is still for sale is the
    routine half of the job, and putting a manager in the way of it is how you
    end up with the expiry sweep being switched off.
    """

    permission_classes = [IsSales]

    @extend_schema(
        request=inline_serializer('ExtendListing', {
            'days': serializers.IntegerField(required=False),
        }),
        responses={200: StaffCarSerializer},
        description="Push a listing's expiry out from now. Defaults to "
                    "LISTING_LIFETIME_DAYS.",
    )
    def post(self, request, pk):
        try:
            car = Car.objects.get(pk=pk)
        except Car.DoesNotExist:
            return Response({"error": "not found"}, status=404)

        days = request.data.get("days")
        if days is not None:
            try:
                days = int(days)
            except (TypeError, ValueError):
                return Response({"days": "Must be a whole number of days."}, status=400)
            if days < 1:
                return Response({"days": "Must be at least one day."}, status=400)

        car.extend(days)
        return Response(StaffCarSerializer(car, context={"request": request}).data)


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

    def get_queryset(self):
        queryset = super().get_queryset()
        # ?cancelled=true is the re-engagement worklist - the list of people
        # who walked away and might still be won back.
        cancelled = self.request.query_params.get("cancelled")
        if cancelled in ("true", "1"):
            queryset = queryset.filter(cancelled_at__isnull=False)
        elif cancelled in ("false", "0"):
            queryset = queryset.filter(cancelled_at__isnull=True)
        return queryset


class StaffOrderDetailView(ManagerToDelete, generics.RetrieveUpdateDestroyAPIView):
    queryset = ImportOrder.objects.all()
    serializer_class = StaffOrderSerializer


class StaffReactivateOrderView(APIView):
    """Bring a cancelled order back and tell the customer why.

    The message is required. Reopening an order silently would leave the
    customer to discover it from a tracking page they had stopped watching,
    which is not re-engagement.
    """

    permission_classes = [IsSales]

    @extend_schema(
        request=inline_serializer('ReactivateOrder', {
            'message': serializers.CharField(),
        }),
        responses={200: StaffOrderSerializer},
        description="Reopen a cancelled import order and email the customer a "
                    "reason to come back.",
    )
    def post(self, request, pk):
        try:
            order = ImportOrder.objects.get(pk=pk)
        except ImportOrder.DoesNotExist:
            return Response({"error": "not found"}, status=404)

        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"message": "Say what has changed - an offer, or a unit found."},
                status=400,
            )

        ok, detail = order.reactivate()
        if not ok:
            return Response({"error": detail}, status=400)

        emailed = send_reengagement(order, message)
        data = StaffOrderSerializer(order).data
        # Reported rather than fatal: the order is open either way, and a
        # customer with no address on file still needs chasing by phone.
        data["emailed"] = emailed
        return Response(data)


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

        # Doubles as the resend: a customer who lost the email gets another by
        # dispatching again, rather than staff pasting the URL into a chat.
        emailed = send_payment_instructions(payment, email)

        if payment.method == "card":
            return Response({"checkout_url": detail, "emailed": emailed})
        return Response({
            "detail": f"M-PESA prompt sent to {phone}",
            "emailed": emailed,
        })


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


# --- sourcing --------------------------------------------------------------

class StaffImportRequestListView(generics.ListCreateAPIView):
    queryset = ImportRequest.objects.prefetch_related("units").all()
    serializer_class = StaffImportRequestSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status", "make", "model"]
    search_fields = ["contact_name", "email", "phone", "make", "model"]


class StaffImportRequestDetailView(ManagerToDelete, generics.RetrieveUpdateDestroyAPIView):
    queryset = ImportRequest.objects.prefetch_related("units")
    serializer_class = StaffImportRequestSerializer


class StaffSourcedUnitListView(generics.ListCreateAPIView):
    """Adding a unit against a request is the sourcing step.

    Creating the first one moves the request out of "pending" - the status
    should follow from the work rather than needing to be set separately and
    remembered.
    """

    queryset = SourcedUnit.objects.select_related("request").all()
    serializer_class = StaffSourcedUnitSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["request", "status"]

    def perform_create(self, serializer):
        unit = serializer.save()
        import_request = unit.request
        if import_request.status == "pending":
            import_request.status = "sourcing"
            import_request.save(update_fields=["status"])


class StaffSourcedUnitDetailView(ManagerToDelete, generics.RetrieveUpdateDestroyAPIView):
    queryset = SourcedUnit.objects.select_related("request")
    serializer_class = StaffSourcedUnitSerializer


class StaffNotifySourcedView(APIView):
    """Send the "we found some options" email and hand the choice over."""

    permission_classes = [IsSales]

    @extend_schema(
        request=None,
        responses={200: StaffImportRequestSerializer},
        description="Tell the customer their units are ready to look at.",
    )
    def post(self, request, pk):
        try:
            import_request = ImportRequest.objects.get(pk=pk)
        except ImportRequest.DoesNotExist:
            return Response({"error": "not found"}, status=404)

        if not notify_units_sourced(import_request):
            return Response(
                {"error": "there are no units on offer to tell them about"},
                status=400,
            )

        import_request.status = "awaiting_selection"
        import_request.save(update_fields=["status"])
        return Response(StaffImportRequestSerializer(import_request).data)


class StaffPushToStockView(APIView):
    """The flywheel: a rejected sourced unit becomes a local listing.

    Sales rather than Manager, matching StaffCarListView - creating a listing
    is already something Sales may do, and routing this through a manager
    would leave rejected units sitting unconverted, which is the exact waste
    the feature exists to stop.
    """

    permission_classes = [IsSales]

    @extend_schema(
        request=inline_serializer('PushToStock', {
            'markup_percent': serializers.DecimalField(
                max_digits=5, decimal_places=2, required=False
            ),
        }),
        responses={201: StaffCarSerializer},
        description="Convert a sourced unit into a local listing, priced at "
                    "landed cost plus markup. Defaults to "
                    "PUSH_TO_STOCK_MARKUP_PERCENT.",
    )
    def post(self, request, pk):
        try:
            unit = SourcedUnit.objects.get(pk=pk)
        except SourcedUnit.DoesNotExist:
            return Response({"error": "not found"}, status=404)

        markup = request.data.get("markup_percent")
        if markup is not None:
            try:
                markup = Decimal(str(markup))
            except (ArithmeticError, ValueError):
                return Response(
                    {"markup_percent": "Must be a number."}, status=400
                )
            if markup < 0:
                return Response(
                    {"markup_percent": "Cannot be negative."}, status=400
                )

        car, detail = unit.push_to_stock(markup_percent=markup)
        if car is None:
            return Response({"error": detail}, status=400)

        return Response(
            StaffCarSerializer(car, context={"request": request}).data,
            status=201,
        )


class StaffImportRatesView(APIView):
    """The percentages the landing-cost arithmetic uses.

    Served rather than hardcoded in the frontend so the sourcing screen can
    preview a total live without the rates becoming a second source of truth.
    They move - that is the whole reason they are settings - and a stale copy
    baked into a JS bundle would quote customers the wrong number until
    somebody noticed.
    """

    permission_classes = [IsSales]

    @extend_schema(
        responses={200: inline_serializer('ImportRates', {
            'duty': serializers.DecimalField(max_digits=5, decimal_places=2),
            'excise_default': serializers.DecimalField(max_digits=5, decimal_places=2),
            'vat': serializers.DecimalField(max_digits=5, decimal_places=2),
            'idf': serializers.DecimalField(max_digits=5, decimal_places=2),
            'rdl': serializers.DecimalField(max_digits=5, decimal_places=2),
            'stock_markup': serializers.DecimalField(max_digits=5, decimal_places=2),
            'effective_from': serializers.DateField(),
        })},
        description="KRA rates and the default stock markup, as percentages.",
    )
    def get(self, request):
        rates = ImportRates.current()
        return Response({
            "duty": rates.duty_rate,
            "excise_default": rates.excise_rate,
            "vat": rates.vat_rate,
            "idf": rates.idf_rate,
            "rdl": rates.rdl_rate,
            "stock_markup": rates.stock_markup,
            "effective_from": rates.effective_from,
        })
