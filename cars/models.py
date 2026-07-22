from django.db import models

class Car(models.Model):
    state_choices = [
        ('new', 'New'),
        ('used', 'Used'),
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("sold", "Sold"),
    ]
    make=models.CharField(max_length=50)
    model=models.CharField(max_length=50)
    year=models.PositiveIntegerField()
    price=models.DecimalField(max_digits=12, decimal_places=2)
    state=models.CharField(max_length=10, choices=state_choices, default='available')
    description=models.TextField()

    def __str__(self):
        return f"{self.make} {self.model} ({self.year}) - {self.state} - ${self.price} - {self.description}"
    image=models.ImageField(upload_to='cars/', blank=True)    