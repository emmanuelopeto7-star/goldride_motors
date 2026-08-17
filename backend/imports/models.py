from django.db import models
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from cars.models import Car

def earliest_eligible_year():
    """The oldest model year KEBS will still clear, for this calendar year."""
    return timezone.now().year - settings.IMPORT_MAX_VEHICLE_AGE_YEARS


def validate_import_age(year):
    if year > timezone.now().year:
        raise ValidationError("That model year is in the future.")
    if year < earliest_eligible_year():
        raise ValidationError(
            f"Kenya will not clear a vehicle older than "
            f"{settings.IMPORT_MAX_VEHICLE_AGE_YEARS} years. The oldest we can "
            f"import this year is {earliest_eligible_year()}."
        )


class ImportRequest(models.Model):
    """What a customer asked us to find. Not a car - a specification.

    Guests may raise one without an account, which is why the contact details
    live here rather than being read off a User, and why there is a token: it
    is the only way an unregistered customer can come back to it.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sourcing", "Sourcing"),
        ("awaiting_selection", "Awaiting selection"),
        ("agreed", "Agreement pending"),
        ("cancelled", "Cancelled"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_requests",
    )
    contact_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)

    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveIntegerField(
        validators=[validate_import_age],
        help_text="Desired model year. Refused here if it is too old to clear.",
    )
    budget_kes = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def selected_unit(self):
        return self.units.filter(status="selected").first()

    def __str__(self):
        return f"{self.year} {self.make} {self.model} for {self.contact_name}"


class SourcedUnit(models.Model):
    """A real car, found abroad, offered against a request.

    The distinction that matters: this is a *candidate*, not stock and not an
    order. Most are rejected, which is the whole premise of Push to Stock -
    the finding, grading and costing has already been paid for in staff time.

    Money is held as its inputs rather than as a total. The dollar rate is
    pinned onto the row at quote time because it moves, and a quote given at
    129 that lands at 138 is a loss somebody has to absorb; keeping the rate
    means an old quote can still be read back and understood.
    """

    STATUS_CHOICES = [
        ("offered", "Offered"),
        ("selected", "Selected"),
        ("rejected", "Rejected"),
    ]

    request = models.ForeignKey(
        ImportRequest, on_delete=models.CASCADE, related_name="units"
    )

    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveIntegerField(validators=[validate_import_age])
    chassis_number = models.CharField(max_length=30, blank=True)
    mileage_km = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(
        max_length=10, blank=True, help_text="Auction grade, e.g. 4.5 or R."
    )
    exterior_colour = models.CharField(max_length=40, blank=True)
    auction_sheet_url = models.URLField(blank=True)
    photo = models.ImageField(upload_to="sourced/", blank=True)

    # --- the quote -------------------------------------------------------
    unit_price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    freight_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dollar_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="KES per USD, as quoted. Pinned so an old quote still reads.",
    )
    # Entered rather than computed: KRA assesses duty on its own CRSP
    # valuation depreciated by age, not on what we paid, so there is no
    # formula here that would be honest.
    duty_kes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    clearing_kes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Port, agent and transport charges.",
    )
    # Ours. Without it "total landed cost" is what the import cost us, and
    # quoting that to a customer is quoting at zero margin.
    service_fee_kes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Goldride's commission on this unit.",
    )

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="offered"
    )
    rejected_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # A request results in one car. Two selections would mean two
            # orders against one enquiry, which is what "agreed" denies.
            models.UniqueConstraint(
                fields=["request"],
                condition=models.Q(status="selected"),
                name="one_selected_unit_per_request",
                violation_error_message="This request already has a unit selected.",
            )
        ]

    # --- the waterfall ---------------------------------------------------
    # Derived, never stored. Every input is on the row, so a total can always
    # be rebuilt - and if the formula is ever corrected, old rows correct too.

    @property
    def cnf_usd(self):
        """Cost and Freight: the car, delivered to Mombasa."""
        return self.unit_price_usd + self.freight_usd

    @property
    def cif_usd(self):
        """Cost, Insurance and Freight."""
        return self.cnf_usd + self.insurance_usd

    @property
    def cnf_kes(self):
        return self.cnf_usd * self.dollar_rate

    @property
    def cif_kes(self):
        return self.cif_usd * self.dollar_rate

    @property
    def landed_cost_kes(self):
        """What the unit costs us, delivered and cleared. Not a price."""
        return self.cif_kes + self.duty_kes + self.clearing_kes

    @property
    def total_kes(self):
        """What the customer pays to have it on their driveway."""
        return self.landed_cost_kes + self.service_fee_kes

    def select(self):
        """Take this one. Rejects its siblings - choosing is also declining."""
        if self.status == "rejected":
            return False, "this unit was already rejected"
        if self.request.selected_unit and self.request.selected_unit != self:
            return False, "another unit has already been selected"

        siblings = self.request.units.exclude(pk=self.pk).filter(status="offered")
        siblings.update(status="rejected", rejected_reason="Another unit was chosen")

        self.status = "selected"
        self.save(update_fields=["status"])

        self.request.status = "agreed"
        self.request.save(update_fields=["status"])
        return True, "selected"

    def reject(self, reason=""):
        if self.status == "selected":
            return False, "this unit has already been selected"

        self.status = "rejected"
        self.rejected_reason = reason[:200]
        self.save(update_fields=["status", "rejected_reason"])
        return True, "rejected"

    def __str__(self):
        return f"{self.year} {self.make} {self.model} ({self.get_status_display()})"


class ImportOrder(models.Model):
    STAGE_CHOICES = [
        ("ordered", "Ordered"),
        ("shipped", "Shipped"),
        ("at_port", "At Port"),
        ("clearing", "Customs Clearing"),
        ("delivered", "Delivered"),
    ]
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    car = models.ForeignKey(
        Car,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    car_description = models.CharField(max_length=200)
    current_stage = models.CharField(max_length=10, choices=STAGE_CHOICES, default="ordered")
    created_at = models.DateTimeField(auto_now_add=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Cancellation is orthogonal to the shipping stage - an order can be
    # cancelled at any point along it - so it is a timestamp rather than a
    # sixth stage. Keeping the stage intact is also what makes reactivation
    # possible: we still know how far the order had got.
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_orders",
        help_text="Blank when the customer cancelled it themselves.",
    )
    reactivated_at = models.DateTimeField(null=True, blank=True)

    @property
    def amount_paid(self):
        total = self.payments.filter(status="paid").aggregate(Sum("amount"))["amount__sum"]
        return total or Decimal("0.00")

    @property
    def balance(self):
        return self.total_amount - self.amount_paid

    @property
    def is_settled(self):
        return self.total_amount > 0 and self.balance <= 0

    @property
    def car_title(self):
        """A name you can put in a subject line.

        `car_description` is whatever `str(car)` gave at the time, which trails
        the entire sales description and prices in dollars - fine as a record,
        unusable as a heading. Derived rather than stored so existing orders
        get it too.
        """
        if self.car_id:
            return f"{self.car.year} {self.car.make} {self.car.model}"
        return self.car_description

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None

    def cancel(self, reason="", by=None):
        """Stop an order and put its car back on the market.

        Deliberately not a delete: a cancelled order is the entire input to the
        re-engagement workflow, and the sourcing work behind it still has value.
        """
        if self.is_cancelled:
            return False, "this order is already cancelled"
        if self.current_stage == "delivered":
            return False, "a delivered order cannot be cancelled"

        self.cancelled_at = timezone.now()
        self.cancel_reason = reason[:200]
        self.cancelled_by = by
        self.save(update_fields=["cancelled_at", "cancel_reason", "cancelled_by"])
        self.release_car()
        return True, "cancelled"

    def reactivate(self):
        """Bring a cancelled order back, reserving its car again.

        Refuses if the car was sold to someone else in the meantime - the whole
        point of releasing it on cancellation is that it becomes available, so
        winning it back cannot be assumed.
        """
        if not self.is_cancelled:
            return False, "this order is not cancelled"
        if self.car_id and self.car.availability == "sold":
            return False, "that car has since been sold"

        self.cancelled_at = None
        self.cancel_reason = ""
        self.cancelled_by = None
        self.reactivated_at = timezone.now()
        self.save(update_fields=[
            "cancelled_at", "cancel_reason", "cancelled_by", "reactivated_at",
        ])
        return True, "reactivated"

    def release_car(self):
        """Hand the car back to the lot, unless it has already been sold."""
        if self.car_id:
            Car.objects.filter(pk=self.car_id).exclude(availability="sold").update(
                availability="available"
            )

    def clean(self):
        if not self.car_id:
            return
        # Cancelled orders are excluded: releasing the car is the point of
        # cancelling, and a car back on the lot has to be orderable again.
        clash = (
            ImportOrder.objects.filter(car_id=self.car_id)
            .filter(cancelled_at__isnull=True)
            .exclude(pk=self.pk)
        )
        if clash.exists():
            raise ValidationError(
                {"car": "This car already has an import order against it."}
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # A cancelled order holds nothing. release_car() owns the availability
        # of its car from that point on, so this must not claim it back.
        if self.car_id and not self.is_cancelled:
            state = "sold" if self.current_stage == "delivered" else "reserved"
            Car.objects.filter(pk=self.car_id).exclude(availability=state).update(
                availability=state
            )

    def __str__(self):
        return f"{self.car_description} for {self.customer_name}"
    
class ImportMilestone(models.Model):
    order=models.ForeignKey(ImportOrder, on_delete=models.CASCADE, related_name='milestones')
    stage=models.CharField(max_length=10, choices=ImportOrder.STAGE_CHOICES)
    note=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order} - {self.stage}"    
