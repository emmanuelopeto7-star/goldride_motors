from django.contrib import admin

from .models import Dealer, DealerApplication, DealerListing, DealerListingImage


@admin.register(DealerApplication)
class DealerApplicationAdmin(admin.ModelAdmin):
    list_display = ["dealership_name", "location", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["dealership_name", "contact_name", "email"]


@admin.register(Dealer)
class DealerAdmin(admin.ModelAdmin):
    list_display = ["name", "location", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "contact_name"]


class DealerListingImageInline(admin.TabularInline):
    model = DealerListingImage
    extra = 0


@admin.register(DealerListing)
class DealerListingAdmin(admin.ModelAdmin):
    list_display = ["__str__", "status", "price", "created_at"]
    list_filter = ["status"]
    search_fields = ["make", "model", "dealer__name"]
    inlines = [DealerListingImageInline]
