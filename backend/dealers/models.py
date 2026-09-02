"""Other dealerships listing their cars on Goldride.

Three records, and the split between them is the whole design:

`DealerApplication` is a stranger asking. It carries the first car they want
listed, its photographs, and the paperwork behind it - so the decision to take
a dealership on and the decision to list their car are the same decision, made
once, with the evidence in front of whoever makes it. It raises a ticket like
every other request, so it cannot be lost.

`Dealer` is a dealership we have said yes to. It owns the login.

`DealerListing` is a car a dealer wants listed, and it is **not** a `Car`. That
is deliberate. A dealer's submission has to be invisible to the public until
somebody here has approved it, and the reliable way to guarantee that is for it
to live in a different table entirely - so no missed filter on the storefront
can ever leak one. Approval copies it into a real `Car`, the same way a
sourced unit is pushed to stock.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone

from cars.models import Car, CarImage


# Paperwork is bigger than a photograph and rarer, so it gets its own ceiling.
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {"pdf", "jpg", "jpeg", "png", "webp"}


def validate_document(value):
    """Refuse anything too large or not a document, on a public endpoint.

    Applying needs no account, so this is an unauthenticated upload path: the
    size ceiling and the extension list are the difference between a form and
    somewhere to park arbitrary files.
    """
    if value.size > MAX_DOCUMENT_BYTES:
        raise ValidationError("That file is larger than 10MB.")

    extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
    if extension not in ALLOWED_DOCUMENT_TYPES:
        raise ValidationError("Attach a PDF or an image.")


def document_path(instance, filename):
    """An unguessable directory per file.

    A logbook holds a registration number and an owner's name, and in
    development Django serves MEDIA_ROOT straight off the filesystem. The
    sanctioned way to read one is the staff-only download view; this makes the
    unsanctioned way - guessing the URL - impractical as well as unsupported.
    """
    return f"dealer-documents/{uuid.uuid4().hex}/{filename}"


class DealerApplication(models.Model):
    """Somebody asking to sell a car through us.

    Two kinds of somebody, and the difference is real rather than cosmetic. A
    dealership is a business with a name and a fleet; a private seller is a
    person with one car and an ID number. Asking a person for their "dealership
    name" is how a form tells them they are in the wrong place.

    The type is stored rather than inferred from which fields are filled in:
    inferring it would make an individual who happened to type a trading name
    into the wrong box silently become a dealership.
    """

    INDIVIDUAL = "individual"
    DEALERSHIP = "dealer"
    SELLER_CHOICES = [
        (INDIVIDUAL, "Private seller"),
        (DEALERSHIP, "Dealership"),
    ]

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    seller_type = models.CharField(
        max_length=12, choices=SELLER_CHOICES, default=INDIVIDUAL
    )

    # Blank for a private seller - they are not a business, and a column that
    # insists otherwise would be filled with their own name for no reason.
    dealership_name = models.CharField(max_length=120, blank=True)
    contact_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    location = models.CharField(max_length=120, help_text="Town or city.")

    # A private seller's ID or passport number: the thing that says the person
    # offering the car is the person on its logbook. Staff-only, like every
    # other field here - applications are never readable from a public
    # endpoint. Blank for a dealership, which proves itself with paperwork.
    id_number = models.CharField(max_length=40, blank=True)

    fleet_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Roughly how many cars a dealership has to sell.",
    )
    message = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    decision_note = models.CharField(max_length=200, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_dealer_applications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.display_name} ({self.get_status_display()})"

    @property
    def display_name(self):
        """What to call them on a ticket, in an email, on a staff screen.

        A dealership is its trading name; a private seller is a person. One
        property so the queue, the invitation and the roster cannot disagree.
        """
        if self.seller_type == self.DEALERSHIP and self.dealership_name:
            return self.dealership_name
        return self.contact_name

    @property
    def is_dealership(self):
        return self.seller_type == self.DEALERSHIP


class Dealer(models.Model):
    """An approved seller, and the account they sign in with.

    Named `Dealer` because it began as one and the name is now in a group, a
    permission class, four URLs and every dealer screen; renaming it would
    touch far more than it would clarify. Read it as "somebody approved to
    list cars here" - `seller_type` says which kind.

    OneToOne on the user rather than a group membership alone: the group says
    what they may call, this says whose cars they are.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dealer",
    )
    application = models.OneToOneField(
        DealerApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dealer",
    )

    seller_type = models.CharField(
        max_length=12,
        choices=DealerApplication.SELLER_CHOICES,
        default=DealerApplication.INDIVIDUAL,
    )
    # The trading name for a dealership, the person's name for a private
    # seller. Set from DealerApplication.display_name on approval.
    name = models.CharField(max_length=120)
    contact_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    location = models.CharField(max_length=120)

    # Suspending a dealership stops new submissions without touching the cars
    # of theirs we have already listed and may have taken deposits on.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DealerListing(models.Model):
    """A car a dealer has submitted. Never public until it becomes a `Car`."""

    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    STATUS_CHOICES = [
        (SUBMITTED, "Submitted"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (WITHDRAWN, "Withdrawn"),
    ]

    # A listing arrives one of two ways: attached to an application, from a
    # dealership that does not exist yet, or submitted later through the portal
    # by one that does. Both end up here so there is exactly one path into
    # inventory - `publish()` - rather than a second one nobody tests.
    dealer = models.ForeignKey(
        Dealer,
        on_delete=models.CASCADE,
        related_name="listings",
        null=True,
        blank=True,
    )
    # Kept after approval rather than cleared: it is the record of where this
    # car came from, and the application is what staff reviewed.
    application = models.ForeignKey(
        DealerApplication,
        on_delete=models.CASCADE,
        related_name="listings",
        null=True,
        blank=True,
    )

    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    condition = models.CharField(
        max_length=5, choices=Car.condition_choices, default="used"
    )
    description = models.TextField(blank=True)

    # The same optional spec sheet a Car carries, so approval is a copy rather
    # than a translation and nothing a dealer typed is silently dropped.
    mileage_km = models.PositiveIntegerField(null=True, blank=True)
    engine_cc = models.PositiveIntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=10, choices=Car.fuel_choices, blank=True)
    transmission = models.CharField(
        max_length=10, choices=Car.transmission_choices, blank=True
    )
    drivetrain = models.CharField(
        max_length=3, choices=Car.drivetrain_choices, blank=True
    )
    body_type = models.CharField(max_length=12, choices=Car.body_choices, blank=True)
    exterior_colour = models.CharField(max_length=40, blank=True)
    interior_colour = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=80, blank=True)
    vin = models.CharField(max_length=17, blank=True)

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=SUBMITTED
    )
    decision_note = models.CharField(max_length=200, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_dealer_listings",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # The listing this became. SET_NULL rather than CASCADE: taking a car off
    # the site must not erase the record of who submitted it.
    published_as = models.OneToOneField(
        Car,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dealer_listing",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # A car nobody owns is a car nobody can be asked about.
            models.CheckConstraint(
                condition=(
                    models.Q(dealer__isnull=False)
                    | models.Q(application__isnull=False)
                ),
                name="listing_belongs_to_someone",
            ),
        ]

    def __str__(self):
        return f"{self.year} {self.make} {self.model} - {self.owner_name}"

    @property
    def owner_name(self):
        """Whose car it is, before or after there is an account for them."""
        if self.dealer_id:
            return self.dealer.name
        if self.application_id:
            return f"{self.application.dealership_name} (applying)"
        return "unassigned"

    @property
    def owner_location(self):
        if self.dealer_id:
            return self.dealer.location
        if self.application_id:
            return self.application.location
        return ""

    @property
    def is_editable(self):
        """Once it is on the site it is ours to maintain, not theirs to edit.

        A dealer editing an approved listing would change a record the buyer
        may already have been quoted from, and would not change the `Car` the
        buyer is actually looking at - two figures, one car.
        """
        return self.status in (self.SUBMITTED, self.REJECTED)

    def publish(self):
        """Copy this into a real listing. Idempotent by the guard, not by luck.

        Mirrors SourcedUnit.push_to_stock: the public table only ever receives
        rows a person here has approved.
        """
        if self.published_as_id:
            return None, "this listing is already on the site"

        car = Car.objects.create(
            make=self.make,
            model=self.model,
            year=self.year,
            price=self.price,
            condition=self.condition,
            availability="available",
            description=self.description or self.default_description(),
            mileage_km=self.mileage_km,
            engine_cc=self.engine_cc,
            fuel_type=self.fuel_type,
            transmission=self.transmission,
            drivetrain=self.drivetrain,
            body_type=self.body_type,
            exterior_colour=self.exterior_colour,
            interior_colour=self.interior_colour,
            location=self.location or self.owner_location,
            vin=self.vin,
        )

        photos = list(self.images.all())
        for index, photo in enumerate(photos):
            # Copied, not shared: a dealer deleting their submission later
            # must not blank the photographs on a live listing.
            content = ContentFile(photo.image.read())
            name = photo.image.name.rsplit("/", 1)[-1]
            if index == 0:
                car.image.save(name, content, save=True)
            else:
                gallery = CarImage(car=car)
                gallery.image.save(name, content, save=False)
                gallery.save()

        self.published_as = car
        self.published_at = timezone.now()
        self.save(update_fields=["published_as", "published_at"])
        return car, "listed"

    def default_description(self):
        """Something truthful to start from when the dealer left it blank.

        It does not name the dealership. A car listed through a dealer reads as
        one of ours to the buyer, and a generated description is the one place
        that decision could quietly leak - the record of whose car it is lives
        on this row, where staff can see it and the public cannot.
        """
        parts = [f"{self.year} {self.make} {self.model}."]
        if self.mileage_km:
            parts.append(f"{self.mileage_km:,} km.")
        if self.exterior_colour:
            parts.append(f"Finished in {self.exterior_colour.lower()}.")
        location = self.location or self.owner_location
        if location:
            parts.append(f"Available in {location}.")
        return " ".join(parts)


class DealerListingImage(models.Model):
    """Photographs on a submission. The first one becomes the main image."""

    listing = models.ForeignKey(
        DealerListing, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="dealer-listings/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at", "id"]

    def __str__(self):
        return f"Photo for {self.listing}"


class DealerDocument(models.Model):
    """Paperwork attached to an application.

    The dealership list is what Kenya actually requires of a motor vehicle
    dealer - business registration, KRA PIN, county trade licence, directors'
    ID, the NTSA dealer's application form, a headed application letter and
    insurance - rather than a generic "attach something". Naming each one is
    what lets the form tell an applicant which is missing instead of leaving
    them to guess, and lets staff see a gap at a glance.

    **Never public, and never served from MEDIA.** These carry personal data -
    a logbook names the registered owner, an ID is an ID, a certificate of
    incorporation names directors - so no serializer exposes the file's URL and
    the only way to read one is the staff-only download view, which checks the
    caller first. Photographs are the opposite and end up on the storefront;
    keeping the two in separate models is what stops a future change treating
    them alike.
    """

    LOGBOOK = "logbook"
    ID_DOCUMENT = "id"
    KRA_PIN = "kra_pin"
    VAT_CERTIFICATE = "vat"
    BUSINESS_REGISTRATION = "business_reg"
    TRADE_LICENCE = "trade_licence"
    DEALER_FORM = "dealer_form"
    APPLICATION_LETTER = "letter"
    INSURANCE = "insurance"
    IMPORT_ENTRY = "import_entry"
    OTHER = "other"
    KIND_CHOICES = [
        (BUSINESS_REGISTRATION, "Certificate of incorporation or business registration"),
        (KRA_PIN, "KRA PIN certificate"),
        (VAT_CERTIFICATE, "VAT certificate"),
        (TRADE_LICENCE, "Trade licence (county permit)"),
        (ID_DOCUMENT, "National ID or passport"),
        (DEALER_FORM, "Dealer's application form"),
        (APPLICATION_LETTER, "Headed application letter"),
        (INSURANCE, "Insurance certificate"),
        (LOGBOOK, "Logbook"),
        (IMPORT_ENTRY, "Import entry"),
        (OTHER, "Other"),
    ]

    # What an application is not accepted without.
    #
    # A dealership sends what the licensing process itself demands. VAT is
    # deliberately NOT on this list: registration only bites above the turnover
    # threshold, so requiring it would refuse every dealer below it. Insurance
    # is, because a business moving other people's cars without cover is the
    # one gap here that becomes our problem.
    REQUIRED_OF_DEALERSHIP = [
        BUSINESS_REGISTRATION,
        KRA_PIN,
        TRADE_LICENCE,
        ID_DOCUMENT,
        DEALER_FORM,
        APPLICATION_LETTER,
        INSURANCE,
    ]

    # A private seller is not being licensed - they are selling one car - so
    # the question is only whether they are who they say and whether the car is
    # theirs to sell.
    REQUIRED_OF_INDIVIDUAL = [ID_DOCUMENT, LOGBOOK]

    @classmethod
    def required_for(cls, seller_type):
        if seller_type == DealerApplication.DEALERSHIP:
            return list(cls.REQUIRED_OF_DEALERSHIP)
        return list(cls.REQUIRED_OF_INDIVIDUAL)

    application = models.ForeignKey(
        DealerApplication, on_delete=models.CASCADE, related_name="documents"
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=OTHER)
    file = models.FileField(upload_to=document_path, validators=[validate_document])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at", "id"]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.application.dealership_name}"

    @property
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1]
