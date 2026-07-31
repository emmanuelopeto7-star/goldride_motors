from django.contrib import admin

from .models import ImportOrder, ImportMilestone

from payments.models import Payment

class MilestoneInline(admin.TabularInline):
    model = ImportMilestone
    extra = 1
    readonly_fields = ['created_at']

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = ["reference", "amount", "method", "status", "provider_ref", "created_at"]    

class ImportOrderAdmin(admin.ModelAdmin):
    list_display = [
        "customer_name",
        "customer",
        "car_description",
        "current_stage",
        "total_amount",
        "amount_paid",
        "balance",
        "created_at",
    ]
    list_filter = ["current_stage"]
    search_fields = ["customer_name", "phone", "car_description", "customer__username"]
    readonly_fields = ["token", "created_at", "amount_paid", "balance", "is_settled"]
    inlines = [MilestoneInline, PaymentInline]

    

admin.site.register(ImportOrder, ImportOrderAdmin)    