from django.contrib import admin

from .models import Payment


class PaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "order", "amount", "method", "status", "created_at"]
    list_filter = ["status", "method"]
    search_fields = ["reference", "provider_ref", "note"]
    readonly_fields = ["reference", "provider_ref", "checkout_request_id", "created_at", "updated_at"]


admin.site.register(Payment, PaymentAdmin)
