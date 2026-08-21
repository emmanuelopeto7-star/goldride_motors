from django.db.models import Count, Max
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework import generics,filters,permissions,status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Car, Favourite, HeroBanner
from .serializers import (
    CarMakeSerializer,
    CarModelSerializer,
    CarSerializer,
    FavouriteSerializer,
    HeroBannerSerializer,
)
from django_filters.rest_framework import DjangoFilterBackend

class carListVeiw(generics.ListAPIView):
    queryset = Car.objects.live().order_by("-id")
    serializer_class = CarSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['make', 'model', 'description']
    filterset_fields = [
        'make', 'model', 'year', 'condition', 'availability',
        'fuel_type', 'transmission', 'drivetrain', 'body_type',
    ]
    ordering_fields = ['price', 'year', 'mileage_km']
class carDetailView(generics.RetrieveAPIView):
    # A lapsed listing 404s rather than rendering, so a stale link from a search
    # engine does not turn into an enquiry about a car that is long gone.
    queryset = Car.objects.live()
    serializer_class = CarSerializer


class CarMakesView(generics.ListAPIView):
    """Every make on the lot with a live count.

    Feeds the header brand strip and the make grid, neither of which can be
    built from a paginated page of cars. Counts match what filtering by that
    make actually returns, which is why expired listings are dropped here too -
    a make offering "3 cars" that lists two would be worse than not showing it.
    """

    serializer_class = CarMakeSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Car.objects.live().values("make")
            .annotate(count=Count("id"))
            .order_by("-count", "make")
        )


class CarModelsView(generics.ListAPIView):
    """Every make/model pairing with a count and one photograph, for the
    model carousel. Unpaginated - it is a browse aid, not a listing."""

    serializer_class = CarModelSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Car.objects.live().values("make", "model")
            # Max over the upload path picks a non-empty one when any car of
            # this model has a photo; "" sorts below every real path.
            .annotate(count=Count("id"), image=Max("image"))
            .order_by("-count", "make", "model")
        )


class FavouriteView(generics.ListCreateAPIView):
    """The caller's own saved cars. Signed in only - there is nobody to save
    them against otherwise."""

    serializer_class = FavouriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favourite.objects.filter(user=self.request.user).select_related("car")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Saving something already saved is not an error, it is a no-op.
        favourite, created = Favourite.objects.get_or_create(
            user=request.user, car=serializer.validated_data["car"]
        )
        out = self.get_serializer(favourite)
        return Response(out.data, status=201 if created else 200)


class FavouriteDestroyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=None,
        responses={204: None},
        description="Unsave a car. Keyed on the car id, not the favourite id.",
    )
    def delete(self, request, car_id):
        favourite = get_object_or_404(Favourite, user=request.user, car_id=car_id)
        favourite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class HeroBannerView(APIView):
    """The active hero, or null. Read-only and public, like the car list."""

    @extend_schema(
        responses={200: HeroBannerSerializer},
        description="The active hero banner, or null when none is set.",
    )
    def get(self, request):
        banner = HeroBanner.objects.filter(is_active=True).first()
        if banner is None:
            return Response(None)
        return Response(HeroBannerSerializer(banner, context={"request": request}).data)