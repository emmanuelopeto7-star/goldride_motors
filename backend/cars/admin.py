from django.contrib import admin
from .models import Car, CarImage, HeroBanner

class CarImageInline(admin.TabularInline):
    model = CarImage
    extra = 3
class CarAdmin(admin.ModelAdmin):
    list_display = [
        "make", "model", "year", "price", "condition", "availability",
        "mileage_km", "location", "expires_at", "is_live",
    ]
    list_filter = ["condition", "availability", "make", "fuel_type", "body_type"]
    search_fields = ["make", "model", "description", "vin", "reference"]
    ordering = ["year"]
    inlines = [CarImageInline]
    actions = ["extend_listings"]

    @admin.display(boolean=True, description="Live")
    def is_live(self, obj):
        return not obj.is_expired

    @admin.action(description="Renew selected listings")
    def extend_listings(self, request, queryset):
        for car in queryset:
            car.extend()
        self.message_user(request, f"Renewed {queryset.count()} listing(s).")
    fieldsets = [
        (None, {
            "fields": [
                "make", "model", "year", "price", "condition", "availability",
                "description", "image",
            ],
        }),
        ("Specification", {
            "fields": [
                "mileage_km", "engine_cc", "fuel_type", "transmission",
                "drivetrain", "body_type", "exterior_colour", "interior_colour",
            ],
        }),
        ("Admin", {
            "fields": ["location", "vin", "reference", "expires_at"],
        }),
    ]
admin.site.register(Car, CarAdmin)


class HeroBannerAdmin(admin.ModelAdmin):
    list_display = ["headline", "is_active", "has_video", "updated_at"]
    list_filter = ["is_active"]

    @admin.display(boolean=True, description="Video")
    def has_video(self, obj):
        return bool(obj.video)


admin.site.register(HeroBanner, HeroBannerAdmin)
