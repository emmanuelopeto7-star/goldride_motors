from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models


def validate_hero_video_size(value):
    """A hero that takes ten seconds to arrive is worse than a still one."""
    limit = 5 * 1024 * 1024
    if value.size > limit:
        raise ValidationError("Keep the hero video under 5MB.")

class Car(models.Model):
    condition_choices = [
        ('new', 'New'),
        ('used', 'Used'),      
    ]
    avilability_choices=[
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("sold", "Sold"),
    ]
    fuel_choices = [
        ("petrol", "Petrol"),
        ("diesel", "Diesel"),
        ("hybrid", "Hybrid"),
        ("electric", "Electric"),
    ]
    transmission_choices = [
        ("automatic", "Automatic"),
        ("manual", "Manual"),
    ]
    drivetrain_choices = [
        ("2wd", "2WD"),
        ("awd", "AWD"),
        ("4wd", "4WD"),
    ]
    body_choices = [
        ("suv", "SUV"),
        ("saloon", "Saloon"),
        ("hatchback", "Hatchback"),
        ("coupe", "Coupe"),
        ("pickup", "Pickup"),
        ("van", "Van"),
        ("convertible", "Convertible"),
    ]

    make=models.CharField(max_length=50)
    model=models.CharField(max_length=50)
    year=models.PositiveIntegerField()
    price=models.DecimalField(max_digits=12, decimal_places=2)
    condition=models.CharField(max_length=5, choices=condition_choices, default='used')
    availability=models.CharField(max_length=10, choices=avilability_choices, default='available')
    description=models.TextField()

    # Spec sheet. All optional - a car can be listed before every figure is
    # confirmed, and the detail page simply omits whatever is blank.
    mileage_km = models.PositiveIntegerField(null=True, blank=True)
    engine_cc = models.PositiveIntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=10, choices=fuel_choices, blank=True)
    transmission = models.CharField(
        max_length=10, choices=transmission_choices, blank=True
    )
    drivetrain = models.CharField(max_length=3, choices=drivetrain_choices, blank=True)
    body_type = models.CharField(max_length=12, choices=body_choices, blank=True)
    exterior_colour = models.CharField(max_length=40, blank=True)
    interior_colour = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=80, blank=True)
    # The one field that identifies a physical vehicle. Blank is allowed - a car
    # can be listed before the logbook is in hand - but two listings may not
    # claim the same one, which is what stops a seller listing the same unit
    # twice or inventing a car that does not exist.
    vin = models.CharField(
        max_length=17,
        blank=True,
        verbose_name="VIN / chassis number",
        help_text="Chassis number for Japanese imports. Leave blank until "
                  "confirmed - but once set it must be unique across listings.",
    )
    reference = models.CharField(max_length=40, blank=True)

    # Blank for our own photography. Filled when an image is used under a
    # licence that requires crediting the photographer - CC BY-SA and similar.
    photo_credit = models.CharField(max_length=200, blank=True)
    photo_source = models.URLField(blank=True)

    class Meta:
        constraints = [
            # Conditional, because "no VIN yet" is a normal state and every
            # blank would otherwise collide with every other blank. Uniqueness
            # is only meaningful once someone has actually filled it in.
            models.UniqueConstraint(
                fields=["vin"],
                condition=~models.Q(vin=""),
                name="unique_vin_when_set",
                violation_error_message="Another listing already uses this VIN / chassis number.",
            )
        ]

    def normalise_vin(self):
        """Uppercase and trim, so the constraint above catches 'abc' vs 'ABC '.

        Cheaper and more portable than a case-insensitive index: store one
        canonical form and a plain unique constraint does the work.
        """
        if self.vin:
            self.vin = self.vin.strip().upper()

    def clean(self):
        # Runs before validate_constraints() in full_clean(), so the admin
        # compares the normalised value rather than whatever was typed.
        self.normalise_vin()
        super().clean()

    def save(self, *args, **kwargs):
        self.normalise_vin()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.make} {self.model} ({self.year}) - {self.condition} - ${self.price} - {self.description}"
    image=models.ImageField(upload_to='cars/', blank=True)

class Favourite(models.Model):
    """A car someone has saved. CASCADE both ways: a saved car is a bookmark,
    not a record worth outliving either side of it."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favourites"
    )
    car = models.ForeignKey(
        Car, on_delete=models.CASCADE, related_name="favourited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Saving twice is the same as saving once.
            models.UniqueConstraint(fields=["user", "car"], name="unique_favourite")
        ]

    def __str__(self):
        return f"{self.user} saved {self.car}"


class CarImage(models.Model):
    car=models.ForeignKey(Car, on_delete=models.CASCADE, related_name='images')
    image=models.ImageField(upload_to='cars/gallery/')

    def __str__(self):
        return f"Image for {self.car}"


class HeroBanner(models.Model):
    """The full-bleed image on the home page.

    Marketing swaps this from the admin instead of asking for a deploy, which
    is the whole reason it is a row and not a file in the React bundle.
    """

    image = models.ImageField(
        upload_to='hero/',
        help_text="Poster frame, always required - it is what renders on the first "
                  "paint, on mobile, and whenever the video cannot play.",
    )
    video = models.FileField(
        upload_to='hero/',
        blank=True,
        validators=[
            FileExtensionValidator(["mp4", "webm"]),
            validate_hero_video_size,
        ],
        help_text="Optional. Muted and looping, desktop only. Strip the audio "
                  "track before uploading.",
    )
    headline = models.CharField(max_length=120)
    subline = models.CharField(max_length=200, blank=True)
    cta_label = models.CharField(max_length=40, blank=True)
    cta_url = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(
        default=False,
        help_text="Only the most recently updated active banner is served.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.headline} ({'active' if self.is_active else 'draft'})"