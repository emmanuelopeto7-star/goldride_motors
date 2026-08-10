from django.db import models
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum

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

    def clean(self):
        if not self.car_id:
            return
        clash = ImportOrder.objects.filter(car_id=self.car_id).exclude(pk=self.pk)
        if clash.exists():
            raise ValidationError(
                {"car": "This car already has an import order against it."}
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.car_id:
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
