from rest_framework import serializers

from .models import (
    Dealer,
    DealerApplication,
    DealerDocument,
    DealerListing,
    DealerListingImage,
)


class DealerApplicationSerializer(serializers.ModelSerializer):
    """The public form. Write-only in effect - see the view.

    The status fields are read-only rather than absent so the same serializer
    can render an application back to staff without a second class that would
    drift out of step with this one.
    """

    seller_type_label = serializers.CharField(
        source="get_seller_type_display", read_only=True
    )
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = DealerApplication
        fields = [
            "id",
            "seller_type",
            "seller_type_label",
            "display_name",
            "dealership_name",
            "contact_name",
            "email",
            "phone",
            "location",
            "id_number",
            "fleet_size",
            "message",
            "status",
            "decision_note",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = ["status", "decision_note", "reviewed_at", "created_at"]

    def validate(self, attrs):
        """Each kind of seller is asked for what actually identifies them.

        Enforced here rather than by making both columns required: a form that
        demands a dealership name from a private seller is a form telling them
        they are in the wrong place, and one that demands an ID number from a
        business is asking a director for their passport.
        """
        seller_type = attrs.get(
            "seller_type",
            getattr(self.instance, "seller_type", DealerApplication.INDIVIDUAL),
        )

        if seller_type == DealerApplication.DEALERSHIP:
            if not (attrs.get("dealership_name") or "").strip():
                raise serializers.ValidationError(
                    {"dealership_name": ["Tell us the name of the dealership."]}
                )
        else:
            if not (attrs.get("id_number") or "").strip():
                raise serializers.ValidationError(
                    {"id_number": ["We need your ID or passport number."]}
                )
            # A private seller has no trading name and no fleet. Cleared
            # rather than refused: they may have been typed in before the
            # seller type was switched, and losing the whole form over that
            # would be unkind.
            attrs["dealership_name"] = ""
            attrs["fleet_size"] = None

        return attrs


class DealerDocumentSerializer(serializers.ModelSerializer):
    """Paperwork, described but never handed over.

    There is deliberately no `file` field: a logbook names a registered owner
    and an ID is an ID, so the bytes come from the staff-only download view
    after it has checked who is asking. Everything here is what a staff screen
    needs to render a row and a download button.
    """

    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    filename = serializers.CharField(read_only=True)
    size = serializers.SerializerMethodField()

    class Meta:
        model = DealerDocument
        fields = ["id", "kind", "kind_label", "filename", "size", "uploaded_at"]

    def get_size(self, document):
        try:
            return document.file.size
        except (OSError, ValueError):
            # The row can outlive the file - an ephemeral filesystem, a
            # restored database. A missing file is not a broken screen.
            return None


class StaffDealerApplicationSerializer(DealerApplicationSerializer):
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.get_username", read_only=True, default=None
    )
    dealer_id = serializers.IntegerField(source="dealer.id", read_only=True, default=None)
    documents = DealerDocumentSerializer(many=True, read_only=True)
    cars = serializers.SerializerMethodField()

    class Meta(DealerApplicationSerializer.Meta):
        fields = DealerApplicationSerializer.Meta.fields + [
            "reviewed_by_name",
            "dealer_id",
            "documents",
            "cars",
        ]

    def get_cars(self, application):
        """What they are applying with. Approving this application lists it."""
        return StaffDealerListingSerializer(
            application.listings.all(), many=True
        ).data


class DealerListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DealerListingImage
        fields = ["id", "image", "uploaded_at"]
        read_only_fields = ["uploaded_at"]


class DealerListingSerializer(serializers.ModelSerializer):
    images = DealerListingImageSerializer(many=True, read_only=True)
    is_editable = serializers.BooleanField(read_only=True)
    # Display strings alongside the raw values, the same as the car serializer,
    # so the front end never has to know that "awd" means AWD.
    condition_label = serializers.CharField(
        source="get_condition_display", read_only=True
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    published_car_id = serializers.IntegerField(
        source="published_as.id", read_only=True, default=None
    )

    class Meta:
        model = DealerListing
        fields = [
            "id",
            "make",
            "model",
            "year",
            "price",
            "condition",
            "condition_label",
            "description",
            "mileage_km",
            "engine_cc",
            "fuel_type",
            "transmission",
            "drivetrain",
            "body_type",
            "exterior_colour",
            "interior_colour",
            "location",
            "vin",
            "status",
            "status_label",
            "decision_note",
            "reviewed_at",
            "published_car_id",
            "published_at",
            "is_editable",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "decision_note",
            "reviewed_at",
            "published_at",
            "created_at",
            "updated_at",
        ]

    def validate_year(self, value):
        # Not the import eligibility rule - that governs what may be brought
        # into the country, and a dealer's car is already here.
        if value < 1950 or value > 2100:
            raise serializers.ValidationError("That is not a model year.")
        return value

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("A listing needs a price.")
        return value


class StaffDealerListingSerializer(DealerListingSerializer):
    # Both default to None: a car attached to an application has no dealership
    # behind it yet, and will not until somebody approves it.
    dealer_name = serializers.CharField(
        source="dealer.name", read_only=True, default=None
    )
    dealer_id = serializers.IntegerField(
        source="dealer.id", read_only=True, default=None
    )
    owner_name = serializers.CharField(read_only=True)
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.get_username", read_only=True, default=None
    )

    class Meta(DealerListingSerializer.Meta):
        fields = DealerListingSerializer.Meta.fields + [
            "dealer_name",
            "dealer_id",
            "owner_name",
            "reviewed_by_name",
        ]


class DealerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    seller_type_label = serializers.CharField(
        source="get_seller_type_display", read_only=True
    )
    listings_live = serializers.SerializerMethodField()
    listings_waiting = serializers.SerializerMethodField()

    class Meta:
        model = Dealer
        fields = [
            "id",
            "seller_type",
            "seller_type_label",
            "name",
            "contact_name",
            "phone",
            "location",
            "email",
            "is_active",
            "created_at",
            "listings_live",
            "listings_waiting",
        ]
        read_only_fields = ["created_at", "email"]

    def get_listings_live(self, dealer):
        return dealer.listings.filter(status=DealerListing.APPROVED).count()

    def get_listings_waiting(self, dealer):
        return dealer.listings.filter(status=DealerListing.SUBMITTED).count()


class DecisionSerializer(serializers.Serializer):
    """Approve or reject, with a note the applicant will read."""

    note = serializers.CharField(required=False, allow_blank=True, max_length=200)


# The car fields the public application form collects, and the DealerListing
# column each one fills. Prefixed on the way in because the whole thing arrives
# as one multipart form - files and all - and a flat body is what a browser
# sends without ceremony.
APPLICATION_CAR_FIELDS = [
    "make", "model", "year", "price", "condition", "description",
    "mileage_km", "fuel_type", "transmission", "body_type",
    "exterior_colour", "location", "vin",
]

MAX_APPLICATION_PHOTOS = 12
MAX_APPLICATION_DOCUMENTS = 14


class DealerApplicationCreateSerializer(DealerApplicationSerializer):
    """Applying, with the first car and the paperwork behind it.

    A dealership and a car in one submission, because that is one errand. The
    car is validated by the same serializer that governs every other listing,
    so a car arriving this way cannot be looser than one submitted through the
    portal later.
    """

    car = serializers.DictField(write_only=True, required=True)

    class Meta(DealerApplicationSerializer.Meta):
        fields = DealerApplicationSerializer.Meta.fields + ["car"]

    def validate_car(self, value):
        listing = DealerListingSerializer(data=value)
        listing.is_valid(raise_exception=True)
        return listing.validated_data
