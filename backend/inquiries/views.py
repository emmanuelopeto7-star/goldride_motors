from rest_framework import generics
from rest_framework.throttling import ScopedRateThrottle

from goldride_app.permissions import IsCustomer, IsSales

from .models import Inquiry
from .serializers import InquirySerializer, StaffInquirySerializer

from django.conf import settings
from goldride_app.mail import send as send_mail


class InquiryCreateView(generics.ListCreateAPIView):
    serializer_class = InquirySerializer
    permission_classes = [IsCustomer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'inquiries'

    def get_queryset(self):
        return Inquiry.objects.filter(customer=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        inquiry = serializer.save(
            customer=user,
            name=serializer.validated_data.get("name") or user.get_full_name() or user.username,
            email=user.email,
        )
        send_mail(
            subject=f"New inquiry: {inquiry.car}",
            message=f"{inquiry.name} ({inquiry.phone}) is interested in {inquiry.car}.\n\n{inquiry.message}",
            to=[settings.SALES_EMAIL],
        )


class InquiryListView(generics.ListAPIView):
    queryset = Inquiry.objects.all().order_by("-created_at")
    serializer_class = StaffInquirySerializer
    permission_classes = [IsSales]
