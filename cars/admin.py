from django.contrib import admin
from .models import Car

class CarAdmin(admin.ModelAdmin):
    list_display = ["make", "model", "year", "price", "condition", "availability"]
    list_filter = ["condition", "availability", "make"]
    search_fields = ["make", "model", "description"]
    ordering = ["year"]
admin.site.register(Car)
