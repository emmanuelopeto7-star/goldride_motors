from rest_framework import generics,filters
from .models import Car
from .serializers import CarSerializer
from django_filters.rest_framework import DjangoFilterBackend

class carListVeiw(generics.ListAPIView):
    queryset = Car.objects.all()
    serializer_class = CarSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['make', 'model', 'year', 'state']
    ordering_fields = ['price', 'year']
class carDetailView(generics.RetrieveAPIView):
    queryset = Car.objects.all()
    serializer_class = CarSerializer