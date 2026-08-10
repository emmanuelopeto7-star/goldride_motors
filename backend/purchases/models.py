from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from cars.models import Car


class PurchaseRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    METHOD_CHOICES = [
        ("mpesa", "M-Pesa"),
        ("card", "Card"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_requests",
    )
    car = models.ForeignKey(
        Car,
        on_delete=models.PROTECT,
        related_name="purchase_requests",
    )
    preferred_method = models.CharField(
        max_length=10, choices=METHOD_CHOICES, default="mpesa"
    )
    phone = models.CharField(max_length=20)
    message = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    decision_note = models.CharField(max_length=200, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_purchase_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    order = models.OneToOneField(
        "imports.ImportOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_request",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if not self.car_id:
            return

        if self.car.availability == "sold":
            raise ValidationError({"car": "This car has already been sold."})

        if self.status == "pending":
            clash = PurchaseRequest.objects.filter(
                car_id=self.car_id, status="pending"
            ).exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError(
                    {"car": "There is already a pending request for this car."}
                )

    def __str__(self):
        return f"{self.customer} wants {self.car} ({self.get_status_display()})"
