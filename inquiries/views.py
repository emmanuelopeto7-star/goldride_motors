from rest_framework import generics
from .models import Inquiry
from .serializers import InquirySerializer
from rest_framework.throttling import ScopedRateThrottle
from django.core.mail import send_mail

class InquiryCreateView(generics.CreateAPIView):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'inquiries'

    def perform_create(self, serializer):
        inquiry = serializer.save()
        send_mail(
            subject=f"New inquiry: {inquiry.car}",
            message=f"{inquiry.name} ({inquiry.phone}) is interested in {inquiry.car}.\n\n{inquiry.message}",
            from_email=None,
            recipient_list=["sales@goldridemotors.co.ke"],
            fail_silently=True,
        )