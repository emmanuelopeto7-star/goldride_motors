from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from cars.models import Car, CarImage, HeroBanner
from imports.models import (
    ImportRates,
    ImportMilestone,
    ImportOrder,
    ImportRequest,
    SourcedUnit,
)
from payments.models import Payment


class StaffCarSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)
    # How many photographs the listing has, card image included. The single
    # most useful column on the inventory screen right now: most of the
    # catalogue has none, and a car cannot sell from a page with no picture.
    photo_count = serializers.SerializerMethodField()

    class Meta:
        model = Car
        fields = [
            "id",
            "make",
            "model",
            "year",
            "price",
            "condition",
            "availability",
            "description",
            "image",
            "vin",
            "reference",
            "expires_at",
            "is_expired",
            "video_url",
            "photo_count",
            # The spec sheet. Left out until now, which meant a listing added
            # through the dashboard had no body type or fuel - so it matched
            # none of the storefront's filters and showed a half-empty detail
            # page. Every one is optional on the model: a car can be listed
            # before each figure is confirmed.
            "mileage_km",
            "engine_cc",
            "fuel_type",
            "transmission",
            "drivetrain",
            "body_type",
            "exterior_colour",
            "interior_colour",
            "location",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_photo_count(self, car):
        # The card image counts. It is a photograph the listing shows, and
        # ?photos=none already treats it as one - a column reading "None"
        # under a car the worklist calls covered is just wrong.
        #
        # The list view prefetches images, so this costs one query for the
        # whole page rather than one per row.
        return car.images.count() + (1 if car.image else 0)

    def validate_vin(self, vin):
        """DRF skips conditional UniqueConstraints when it builds validators, so
        without this the clash surfaces as a 500 from the database instead of a
        400 naming the field."""
        if not vin:
            return vin

        vin = vin.strip().upper()
        clash = Car.objects.filter(vin=vin)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "Another listing already uses this VIN / chassis number."
            )
        return vin


class StaffCarImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarImage
        fields = ["id", "car", "image"]


class StaffMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportMilestone
        fields = ["id", "order", "stage", "note", "created_at"]
        read_only_fields = ["created_at"]


class StaffOrderSerializer(serializers.ModelSerializer):
    amount_paid = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_settled = serializers.BooleanField(read_only=True)
    is_cancelled = serializers.BooleanField(read_only=True)
    milestones = StaffMilestoneSerializer(many=True, read_only=True)

    class Meta:
        model = ImportOrder
        fields = [
            "id",
            "customer",
            "customer_name",
            "phone",
            "car",
            "car_description",
            "current_stage",
            "total_amount",
            "amount_paid",
            "balance",
            "is_settled",
            "is_cancelled",
            "cancelled_at",
            "cancel_reason",
            "reactivated_at",
            "token",
            "created_at",
            "milestones",
        ]
        # Cancelling and reactivating go through their own endpoints so the
        # car's availability is always moved with them.
        read_only_fields = [
            "token", "created_at", "cancelled_at", "reactivated_at",
        ]

    def validate_car(self, car):
        if car is None:
            return car

        if car.availability == "sold":
            raise serializers.ValidationError("This car has already been sold.")

        # Matches ImportOrder.clean(): a cancelled order released its car, so it
        # no longer blocks a new one.
        clash = ImportOrder.objects.filter(car=car, cancelled_at__isnull=True)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "This car already has an import order against it."
            )
        return car


class StaffPaymentSerializer(serializers.ModelSerializer):
    order_display = serializers.StringRelatedField(source="order", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "reference",
            "order",
            "order_display",
            "amount",
            "method",
            "status",
            "provider_ref",
            "checkout_url",
            "checkout_sent_at",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "reference",
            "provider_ref",
            "checkout_url",
            "checkout_sent_at",
            "created_at",
            "updated_at",
        ]


class StaffSourcedUnitSerializer(serializers.ModelSerializer):
    """The full picture, including what the unit cost us.

    Every step of the waterfall is exposed read-only alongside its inputs, so
    the sourcing screen can show the arithmetic as it is typed rather than
    making staff work out where a number came from.
    """

    cnf_usd = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    cif_usd = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    cnf_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    cif_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    landed_cost_kes = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    total_kes = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    import_duty_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    excise_duty_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    vat_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    idf_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    rdl_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    taxes_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    stock_price_preview = serializers.SerializerMethodField()

    class Meta:
        model = SourcedUnit
        fields = [
            "id", "request",
            "make", "model", "year", "chassis_number", "mileage_km", "grade",
            "exterior_colour", "auction_sheet_url", "photo",
            "unit_price_usd", "freight_usd", "insurance_usd", "dollar_rate",
            "excise_rate", "duty_rate", "vat_rate", "idf_rate", "rdl_rate",
            "customs_value_kes",
            "clearing_kes", "service_fee_kes",
            "import_duty_kes", "excise_duty_kes", "vat_kes", "idf_kes", "rdl_kes", "taxes_kes",
            "cnf_usd", "cif_usd", "cnf_kes", "cif_kes",
            "landed_cost_kes", "total_kes",
            "status", "rejected_reason", "created_at",
            "pushed_to_car", "pushed_at", "stock_price_preview",
        ]
        # Selection runs through the customer's own endpoint so that choosing
        # one unit always rejects its siblings; pushing runs through its own
        # so the conversion can refuse a duplicate chassis.
        read_only_fields = [
            "status", "rejected_reason", "created_at", "pushed_to_car",
            "pushed_at",
        ]

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=2))
    def get_stock_price_preview(self, unit):
        """What it would list at, before anyone commits to converting it."""
        return unit.stock_price()


class StaffImportRequestSerializer(serializers.ModelSerializer):
    units = StaffSourcedUnitSerializer(many=True, read_only=True)

    class Meta:
        model = ImportRequest
        fields = [
            "id", "customer", "contact_name", "email", "phone",
            "make", "model", "year", "budget_kes", "notes",
            "status", "token", "created_at", "units",
        ]
        read_only_fields = ["token", "created_at"]


class StaffHeroBannerSerializer(serializers.ModelSerializer):
    """The full-bleed image on the home page.

    `is_live` rather than leaving the frontend to work it out: the rule is
    that the most recently updated *active* banner wins, so several can be
    active at once and only one of them is on the site. Saying which is the
    difference between a screen you can trust and one you have to reason
    about.
    """

    is_live = serializers.SerializerMethodField()

    class Meta:
        model = HeroBanner
        fields = [
            "id", "image", "video", "headline", "subline",
            "cta_label", "cta_url", "is_active", "is_live", "updated_at",
        ]
        read_only_fields = ["updated_at"]

    @extend_schema_field(serializers.BooleanField())
    def get_is_live(self, banner):
        return banner.pk == self.context.get("live_pk")


class StaffImportRatesWriteSerializer(serializers.ModelSerializer):
    """New rates, in force from a date.

    A row rather than an edit. Every quote copies the rates it was worked out
    under onto itself, so the history is what makes an old quote readable -
    overwriting it would leave figures nobody could account for.
    """

    class Meta:
        model = ImportRates
        fields = [
            "id", "duty_rate", "excise_rate", "vat_rate", "idf_rate",
            "rdl_rate", "stock_markup", "effective_from", "note", "created_at",
        ]
        read_only_fields = ["created_at"]
