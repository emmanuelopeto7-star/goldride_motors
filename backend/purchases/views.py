from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from goldride_app.permissions import IsCustomer, IsManager, IsSales

from .models import PurchaseRequest
from .serializers import (
    ApprovalResponseSerializer,
    DecisionSerializer,
    PurchaseRequestSerializer,
    StaffPurchaseRequestSerializer,
)
from .services import approve_request, notify_sales, reject_request


class PurchaseRequestCreateView(generics.ListCreateAPIView):
    serializer_class = PurchaseRequestSerializer
    permission_classes = [IsCustomer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "purchases"

    def get_queryset(self):
        return PurchaseRequest.objects.filter(customer=self.request.user)

    @extend_schema(
        responses={
            201: PurchaseRequestSerializer,
            400: inline_serializer('PurchaseRequestEmailRequired', {
                'detail': serializers.CharField(),
                'code': serializers.CharField(),
            }),
        },
        description="Ask to buy a listed car. Refused with `code: "
                    "email_required` if the account has no email address - "
                    "approval sends a checkout link, which needs somewhere "
                    "to go. Social sign-ins whose provider did not verify an "
                    "address arrive without one (`needs_email` on /api/me/).",
    )
    def post(self, request, *args, **kwargs):
        if not request.user.email:
            return Response(
                {
                    "detail": "Add an email address to your account before "
                              "requesting to buy.",
                    "code": "email_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        purchase_request = serializer.save(customer=self.request.user)
        notify_sales(purchase_request)


class StaffPurchaseRequestListView(generics.ListAPIView):
    serializer_class = StaffPurchaseRequestSerializer
    permission_classes = [IsSales]

    def get_queryset(self):
        queryset = PurchaseRequest.objects.select_related("car", "customer")
        state = self.request.query_params.get("status")
        if state:
            queryset = queryset.filter(status=state)
        return queryset


class ApprovePurchaseRequestView(APIView):
    permission_classes = [IsManager]

    @extend_schema(
        request=DecisionSerializer,
        responses={200: ApprovalResponseSerializer},
        description="Manager only. Creates the import order, reserves the car, "
                    "raises the payment and dispatches collection.",
    )
    def post(self, request, pk):
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            purchase_request = PurchaseRequest.objects.get(pk=pk)
        except PurchaseRequest.DoesNotExist:
            return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)

        payment, dispatched, detail = approve_request(
            purchase_request,
            reviewed_by=request.user,
            note=serializer.validated_data.get("note", ""),
        )

        if payment is None:
            return Response({"error": detail}, status=status.HTTP_400_BAD_REQUEST)

        body = {
            "status": "approved",
            "order": purchase_request.order_id,
            "payment_reference": str(payment.reference),
            "method": payment.method,
            "amount": str(payment.amount),
            "dispatched": dispatched,
        }

        if dispatched and payment.method == "card":
            body["checkout_url"] = detail
        elif dispatched:
            body["detail"] = "M-PESA prompt sent to the customer's phone"
        else:
            body["detail"] = detail

        return Response(body)


class RejectPurchaseRequestView(APIView):
    permission_classes = [IsManager]

    @extend_schema(
        request=DecisionSerializer,
        responses={200: ApprovalResponseSerializer},
        description="Manager only. Declines the request with an optional note.",
    )
    def post(self, request, pk):
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            purchase_request = PurchaseRequest.objects.get(pk=pk)
        except PurchaseRequest.DoesNotExist:
            return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)

        ok, detail = reject_request(
            purchase_request,
            reviewed_by=request.user,
            note=serializer.validated_data.get("note", ""),
        )

        if not ok:
            return Response({"error": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "rejected"})
