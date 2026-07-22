from rest_framework import generics
from .models import Inquiry
from .serializers import InquirySerializer
from rest_framework.throttling import ScopedRateThrottle

class InquiryCreateView(generics.CreateAPIView):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'inquiries'