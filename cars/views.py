from rest_framework import generics
from .models import Car
from .serializers import CarSerializer

class carListVeiw(generics.ListAPIView):
    queryset = Car.objects.all()
    serializer_class = CarSerializer