from django.db import models

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
    make=models.CharField(max_length=50)
    model=models.CharField(max_length=50)
    year=models.PositiveIntegerField()
    price=models.DecimalField(max_digits=12, decimal_places=2)
    condition=models.CharField(max_length=5, choices=condition_choices, default='used')
    availability=models.CharField(max_length=10, choices=avilability_choices, default='available')
    description=models.TextField()

    def __str__(self):
        return f"{self.make} {self.model} ({self.year}) - {self.condition} - ${self.price} - {self.description}"
    image=models.ImageField(upload_to='cars/', blank=True)    

class CarImage(models.Model):
    car=models.ForeignKey(Car, on_delete=models.CASCADE, related_name='images')
    image=models.ImageField(upload_to='cars/gallery/')   

    def __str__(self):
        return f"Image for {self.car}"