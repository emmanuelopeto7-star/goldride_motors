from decimal import Decimal

from django.conf import settings

from drf_spectacular.utils import extend_schema, inline_serializer
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import filters, generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from cars.models import Car, CarImage, HeroBanner
from imports.models import (
    ImportMilestone,
    ImportOrder,
    ImportRates,
    ImportRequest,
    SourcedUnit,
)
from imports.services import notify_units_sourced, send_reengagement
from payments.dispatch import dispatch_payment
from payments.notifications import announce_payment_raised, send_payment_instructions
from payments.pay_link import pay_link
from payments.serializers import (
    CheckoutResponseSerializer,
    CorrectionSerializer,
    DispatchRequestSerializer,
    PaymentEventSerializer,
    ReconciliationRunSerializer,
)
from payments.audit import settle
from payments.models import Payment, PaymentEvent, ReconciliationRun
from payments.sweeper import sweep
from payments.reconciliation import reconcile_payment, reconcile_pending

from .permissions import IsManager, IsSales
from .staff_serializers import (
    StaffImportRatesWriteSerializer,
    StaffHeroBannerSerializer,
    StaffCarImageSerializer,
    StaffCarSerializer,
    StaffImportRequestSerializer,
    StaffMilestoneSerializer,
    StaffOrderSerializer,
    StaffPaymentSerializer,
    StaffSourcedUnitSerializer,
)


class ManagerToDelete:
    """Sales may read and edit; only a Manager may delete.

    Deleting also has to answer for what the row is holding up. Half of these
    models are referenced with PROTECT - a car by its purchase requests, an
    order by its payments - and an unguarded destroy turns that into a 500 and
    a stack trace. The record being protected is usually the correct answer,
    so the refusal says which one rather than failing blankly.
    """

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsManager()]
        return [IsSales()]

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as protected:
            blockers = sorted({obj._meta.verbose_name for obj in protected.protected_objects})
            raise ValidationError({
                "detail": (
                    "This cannot be deleted while it still has "
                    f"{', '.join(blockers)} attached. That history is the "
                    "record of what happened and is kept on purpose."
                ),
                "code": "protected",
            })


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
    """Read the ledger; raise a new invoice on an order.

    Sales, not a manager. Collecting what a customer already agreed to owe is
    the job, not a decision about it - the decisions stay reserved: approving
    a purchase, setting the rates every quote is worked out on, and deleting
    anything. What can be raised here is bounded by the order's outstanding
    balance, which a manager set.

    Raising one tells the customer in the chat thread about the car. Dispatch
    stays a separate endpoint - that is what mails the instructions and pushes
    an M-PESA prompt - so the customer hears about the invoice the moment it
    exists rather than whenever somebody remembers.
    """

    permission_classes = [IsSales]
    # order_display renders str(order) on every row.
    queryset = Payment.objects.select_related("order").order_by("-created_at")
    serializer_class = StaffPaymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "method", "order"]

    def perform_create(self, serializer):
        payment = serializer.save()
        # Stamps checkout_sent_at when it lands, and the response carries it -
        # which is how the dashboard knows whether to say the customer has
        # been told or that this order has no thread to tell them in.
        announce_payment_raised(payment)


class StaffPaymentDispatchView(APIView):
    """Ask the customer for a pending payment, again if need be.

    Sales, alongside raising it. Chasing a payment is the work; a rep who can
    see an unpaid invoice and not send the link is a rep who has to find a
    manager to do the obvious thing. The amount is not theirs to choose - it
    was fixed when the invoice was raised - and the money never touches us.
    """

    permission_classes = [IsSales]

    @extend_schema(
        request=DispatchRequestSerializer,
        responses={200: CheckoutResponseSerializer},
        description="Send a checkout link or an M-PESA prompt for a pending payment.",
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
            # Both: the checkout is what to open right now, the pay link is
            # what to pass on. A Paystack session pasted into a chat is stale
            # by the time somebody reads it.
            return Response({
                "checkout_url": detail,
                "pay_url": pay_link(payment),
                "emailed": emailed,
            })
        return Response({
            "detail": f"M-PESA prompt sent to {phone}",
            "emailed": emailed,
        })


class StaffRecordPaymentView(APIView):
    """Mark a bank transfer received.

    The one payment we cannot ask anybody about. A card payment is believed
    only after re-querying Paystack and an M-PESA one after re-querying
    Safaricom; a transfer into the bank account has no callback, no reference
    of ours, and no API - somebody reads a statement and says so. Until now
    that could only be done in the Django admin, which meant an invoice raised
    for a bank transfer had nowhere to end.

    Manager only, and deliberately narrower than raising or chasing. Those
    ask a customer for money that an agreed order total already says they owe.
    This asserts that money arrived, with nothing behind the assertion but the
    person making it - so it names them in `recorded_by`, and it refuses any
    method a provider could have confirmed instead. Marking a card payment
    paid by hand would defeat the entire re-query-before-believing design.
    """

    permission_classes = [IsManager]

    @extend_schema(
        request=inline_serializer('RecordPayment', {
            'provider_ref': serializers.CharField(),
            'note': serializers.CharField(required=False, allow_blank=True),
        }),
        responses={200: StaffPaymentSerializer},
        description="Manager only. Record a pending bank transfer as received, "
                    "against the reference it arrived under.",
    )
    def post(self, request, reference):
        bank_ref = (request.data.get("provider_ref") or "").strip()
        if not bank_ref:
            return Response(
                {"error": "the bank reference it arrived under is required"},
                status=400,
            )

        # Locked and re-read inside the transaction: two managers looking at
        # the same statement would otherwise both record it, and the second
        # write would silently overwrite the first one's name.
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .filter(reference=reference)
                .first()
            )
            if payment is None:
                return Response({"error": "no payment with that reference"}, status=404)

            if payment.method != "manual":
                return Response(
                    {"error": "only a bank transfer is recorded by hand - ask the "
                              "provider about this one instead"},
                    status=400,
                )

            if payment.status != "pending":
                return Response(
                    {"error": f"this payment is already {payment.status}"},
                    status=400,
                )

            payment.provider_ref = bank_ref[:100]
            payment.recorded_by = request.user
            payment.recorded_at = timezone.now()
            note = (request.data.get("note") or "").strip()
            if note:
                payment.note = note[:200]
            payment.save(update_fields=[
                "provider_ref", "recorded_by", "recorded_at",
                "note", "updated_at",
            ])

        # Outside the block above, because settle() takes the lock itself and
        # is the only thing allowed to write a status. It records who said so,
        # which for a bank transfer is the only evidence there is.
        settle(
            payment,
            to_status="paid",
            source=PaymentEvent.RECORDED,
            actor=request.user,
            detail=f"bank reference {bank_ref}" if bank_ref else "recorded by hand",
        )

        payment.refresh_from_db()
        return Response(StaffPaymentSerializer(payment).data)


class StaffCorrectPaymentView(APIView):
    """Put a payment right when the rails got it wrong.

    A manager's, not sales': this is the one endpoint that overrules what a
    provider said, and it can move a payment out of any state - that is what
    makes it a correction rather than a settlement.

    Nothing is overwritten. The status changes and a PaymentEvent records what
    it was, what it became, who did it and why - so a payment that reads `paid`
    because somebody here said so is distinguishable forever from one Paystack
    confirmed.
    """

    permission_classes = [IsManager]

    @extend_schema(
        request=CorrectionSerializer,
        responses={200: StaffPaymentSerializer},
        description="Correct a payment's status by hand. Requires a reason, "
                    "which is kept in the payment's history.",
    )
    def post(self, request, reference):
        payment = Payment.objects.filter(reference=reference).first()
        if payment is None:
            return Response({"error": "not found"}, status=404)

        form = CorrectionSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        changed, message = settle(
            payment,
            to_status=form.validated_data["status"],
            source=PaymentEvent.CORRECTION,
            # None: a correction is allowed to move a payment out of whatever
            # state it is in, including one a provider set.
            expected_status=None,
            actor=request.user,
            detail=form.validated_data["reason"],
        )
        if not changed:
            return Response({"error": message}, status=409)

        payment.refresh_from_db()
        return Response(StaffPaymentSerializer(payment).data)


class StaffPaymentHistoryView(APIView):
    """Everything that has ever happened to one payment.

    Readable by sales as well as managers: an agent fielding "I paid on
    Tuesday" needs the history to answer it, and only the correcting is a
    manager's job.
    """

    permission_classes = [IsSales]

    @extend_schema(
        responses={200: PaymentEventSerializer(many=True)},
        description="The audit trail for one payment.",
    )
    def get(self, request, reference):
        payment = (
            Payment.objects.filter(reference=reference)
            .prefetch_related("events__actor")
            .first()
        )
        if payment is None:
            return Response({"error": "not found"}, status=404)

        return Response(
            {
                "reference": str(payment.reference),
                "status": payment.status,
                "events": PaymentEventSerializer(
                    payment.events.all(), many=True
                ).data,
            }
        )


class StaffReconciliationRunsView(APIView):
    """Whether the sweep is alive, and what the last ones did.

    "Last checked 6 minutes ago" is the difference between trusting the
    payments screen and quietly not.
    """

    permission_classes = [IsSales]

    @extend_schema(
        responses={200: ReconciliationRunSerializer(many=True)},
        description="Recent reconciliation sweeps, newest first.",
    )
    def get(self, request):
        runs = ReconciliationRun.objects.all()[:20]
        return Response(
            {
                "interval_minutes": settings.RECONCILE_INTERVAL_MINUTES,
                "runs": ReconciliationRunSerializer(runs, many=True).data,
            }
        )


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
        # Through the sweeper rather than reconcile_pending directly, so a
        # button press is recorded and locked exactly like the timed sweep -
        # otherwise a member of staff clicking during an automatic run would
        # have both asking Paystack about the same payments at once.
        run = sweep(trigger=ReconciliationRun.STAFF, stale_minutes=0)
        return Response({
            "checked": run.checked,
            "updated": run.updated,
            "state": run.state,
            "detail": run.error or "",
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

    # Reading them is Sales - the sourcing screen needs them to preview a
    # total. Writing them is a Manager: these decide what every future quote
    # charges a customer.
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsManager()]
        return [IsSales()]

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
        return Response(self._as_percentages(ImportRates.current()))

    @extend_schema(
        request=StaffImportRatesWriteSerializer,
        responses={201: StaffImportRatesWriteSerializer},
        description="Put new rates in force from a given date. Manager only. "
                    "This adds a row rather than editing one: an old quote "
                    "has the rates it was worked out under copied onto it, "
                    "and the record of what was charged has to stay readable.",
    )
    def post(self, request):
        serializer = StaffImportRatesWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            self._as_percentages(ImportRates.current()),
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _as_percentages(rates):
        return {
            "duty": rates.duty_rate,
            "excise_default": rates.excise_rate,
            "vat": rates.vat_rate,
            "idf": rates.idf_rate,
            "rdl": rates.rdl_rate,
            "stock_markup": rates.stock_markup,
            "effective_from": rates.effective_from,
        }


class HeroBannerMixin:
    """Both hero views need the same answer to "which one is actually live?"."""

    permission_classes = [IsSales]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        live = HeroBanner.objects.filter(is_active=True).first()
        context["live_pk"] = live.pk if live else None
        return context


class StaffHeroBannerListView(HeroBannerMixin, generics.ListCreateAPIView):
    """Swapping the home page hero without a deploy - or, until now, without
    the Django admin, which was the only place this could be done."""

    queryset = HeroBanner.objects.all()
    serializer_class = StaffHeroBannerSerializer
    pagination_class = None


class StaffHeroBannerDetailView(
    HeroBannerMixin, ManagerToDelete, generics.RetrieveUpdateDestroyAPIView
):
    queryset = HeroBanner.objects.all()
    serializer_class = StaffHeroBannerSerializer
