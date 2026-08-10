from django.contrib import admin
from .models import Car, CarImage

class CarImageInline(admin.TabularInline):
    model = CarImage
    extra = 3
class CarAdmin(admin.ModelAdmin):
    list_display = ["make", "model", "year", "price", "condition", "availability"]
    list_filter = ["condition", "availability", "make"]
    search_fields = ["make", "model", "description"]
    ordering = ["year"]
    inlines = [CarImageInline]
admin.site.register(Car, CarAdmin)
