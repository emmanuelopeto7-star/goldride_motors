from django.db import models
from cars.models import Car

class Inquiry(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='inquiries')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
         return f"{self.name} about {self.car}"
    

