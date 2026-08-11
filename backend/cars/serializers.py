from rest_framework import serializers

from .models import Car, CarImage, HeroBanner


class CarMakeSerializer(serializers.Serializer):
    """Not a model serializer - the rows come from values()/annotate()."""

    make = serializers.CharField()
    count = serializers.IntegerField()


class HeroBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroBanner
        fields = [
            'id', 'image', 'video', 'headline', 'subline', 'cta_label', 'cta_url',
        ]


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
        ]