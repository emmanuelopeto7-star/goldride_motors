from rest_framework import generics
from .models import Inquiry
from .serializers import InquirySerializer

class InquiryCreateView(generics.CreateAPIView):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer