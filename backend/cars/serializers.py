from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Car, CarImage, Favourite, HeroBanner


class CarMakeSerializer(serializers.Serializer):
    """Not a model serializer - the rows come from values()/annotate()."""

    make = serializers.CharField()
    count = serializers.IntegerField()


class CarModelSerializer(serializers.Serializer):
    """Rows come from values()/annotate(), so image is a raw upload path rather
    than a FileField and has to be turned into a URL by hand."""

    make = serializers.CharField()
    model = serializers.CharField()
    count = serializers.IntegerField()
    image = serializers.SerializerMethodField()

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image(self, row):
        path = row.get("image")
        if not path:
            return None
        request = self.context.get("request")
        url = f"{settings.MEDIA_URL}{path}"
        return request.build_absolute_uri(url) if request else url


class CarImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarImage
        fields = ["id", "image"]


class CarSerializer(serializers.ModelSerializer):
    images = CarImageSerializer(many=True, read_only=True)

    # Display labels, so the frontend never has to know that "awd" means "AWD".
    fuel_type_label = serializers.CharField(
        source='get_fuel_type_display', read_only=True
    )
    transmission_label = serializers.CharField(
        source='get_transmission_display', read_only=True
    )
    drivetrain_label = serializers.CharField(
        source='get_drivetrain_display', read_only=True
    )
    body_type_label = serializers.CharField(
        source='get_body_type_display', read_only=True
    )
    # The player URL, so the detail page can drop it straight into an iframe
    # without knowing the difference between a watch link and an embed link.
    video_embed_url = serializers.CharField(read_only=True)

    class Meta:
        model = Car
        fields = [
            'id', 'make', 'model', 'year', 'price', 'condition', 'availability',
            'description', 'image', 'images',
            'mileage_km', 'engine_cc',
            'fuel_type', 'fuel_type_label',
            'transmission', 'transmission_label',
            'drivetrain', 'drivetrain_label',
            'body_type', 'body_type_label',
            'exterior_colour', 'interior_colour', 'location', 'vin', 'reference',
            'expires_at', 'video_url', 'video_embed_url',
        ]


class FavouriteSerializer(serializers.ModelSerializer):
    """Write a car id, read the whole car back - the saved list is a grid of
    cards, so it needs everything a card needs."""

    car = serializers.PrimaryKeyRelatedField(queryset=Car.objects.all())
    car_detail = serializers.SerializerMethodField()

    class Meta:
        model = Favourite
        fields = ["id", "car", "car_detail", "created_at"]
        read_only_fields = ["id", "created_at"]

    @extend_schema_field(CarSerializer)
    def get_car_detail(self, favourite):
        return CarSerializer(favourite.car, context=self.context).data


class HeroBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroBanner
        fields = [
            'id', 'image', 'video', 'headline', 'subline', 'cta_label', 'cta_url',
        ]
