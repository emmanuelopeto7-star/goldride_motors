from django.db import models
import uuid

class ImportOrder(models.Model):
    STAGE_CHOICES = [
        ("ordered", "Ordered"),
        ("shipped", "Shipped"),
        ("at_port", "At Port"),
        ("clearing", "Customs Clearing"),
        ("delivered", "Delivered"),
    ]
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    car_description = models.CharField(max_length=200)
    current_stage = models.CharField(max_length=10, choices=STAGE_CHOICES, default="ordered")
    created_at = models.DateTimeField(auto_now_add=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def __str__(self):
        return f"{self.car_description} for {self.customer_name}"
    
class ImportMilestone(models.Model):
    order=models.ForeignKey(ImportOrder, on_delete=models.CASCADE, related_name='milestones')
    stage=models.CharField(max_length=10, choices=ImportOrder.STAGE_CHOICES)
    note=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order} - {self.stage}"    
