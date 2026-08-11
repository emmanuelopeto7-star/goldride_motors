from django.db.models import Count
from rest_framework import generics,filters
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Car, HeroBanner
from .serializers import CarMakeSerializer, CarSerializer, HeroBannerSerializer
from django_filters.rest_framework import DjangoFilterBackend

class carListVeiw(generics.ListAPIView):
    queryset = Car.objects.all().order_by("-id")
    serializer_class = CarSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['make', 'model', 'description']
    filterset_fields = [
        'make', 'model', 'year', 'condition', 'availability',
        'fuel_type', 'transmission', 'drivetrain', 'body_type',
    ]
    ordering_fields = ['price', 'year', 'mileage_km']
class carDetailView(generics.RetrieveAPIView):
    queryset = Car.objects.all()
    serializer_class = CarSerializer


class CarMakesView(generics.ListAPIView):
    """Every make on the lot with a live count.

    Feeds the header brand strip and the make grid, neither of which can be
    built from a paginated page of cars. Counts match what filtering by that
    make actually returns, so nothing is excluded here.
    """

    serializer_class = CarMakeSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Car.objects.values("make")
            .annotate(count=Count("id"))
            .order_by("-count", "make")
        )


class HeroBannerView(APIView):
    """The active hero, or null. Read-only and public, like the car list."""

    def get(self, request):
        banner = HeroBanner.objects.filter(is_active=True).first()
        if banner is None:
            return Response(None)
        return Response(HeroBannerSerializer(banner, context={"request": request}).data)