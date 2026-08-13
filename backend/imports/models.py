from django.db import models
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from cars.models import Car

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
