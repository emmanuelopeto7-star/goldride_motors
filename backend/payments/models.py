from django.db import models
import uuid
from imports.models import ImportOrder

class Payment(models.Model):
    METHOD_CHOICES = [
        ("mpesa", "M-Pesa"),
        ("card", "Card"),
        ("manual", "Manual / Bank"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey(ImportOrder, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    provider_ref = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    paystack_ref = models.CharField(max_length=100, blank=True)
    checkout_url = models.URLField(max_length=300, blank=True)
    # When the customer was told how to pay. Blank means they have not been,
    # which is the difference between "waiting on them" and "waiting on us".
    checkout_sent_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.amount} KES - {self.get_status_display()} - {self.order}"
