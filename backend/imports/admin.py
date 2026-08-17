from django.contrib import admin

from .models import ImportMilestone, ImportOrder, ImportRequest, SourcedUnit

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
        "car",
        "car_description",
        "current_stage",
        "total_amount",
        "amount_paid",
        "balance",
        "is_cancelled",
        "created_at",
    ]
    list_filter = ["current_stage", "cancelled_at"]
    search_fields = ["customer_name", "phone", "car_description", "customer__username"]
    readonly_fields = [
        "token", "created_at", "amount_paid", "balance", "is_settled",
        "cancelled_at", "reactivated_at",
    ]
    inlines = [MilestoneInline, PaymentInline]
    actions = ["cancel_orders"]

    @admin.display(boolean=True, description="Cancelled")
    def is_cancelled(self, obj):
        return obj.is_cancelled

    @admin.action(description="Cancel selected orders and release their cars")
    def cancel_orders(self, request, queryset):
        cancelled = 0
        for order in queryset:
            ok, _ = order.cancel(reason="Cancelled by staff", by=request.user)
            cancelled += 1 if ok else 0
        self.message_user(request, f"Cancelled {cancelled} order(s).")

    

admin.site.register(ImportOrder, ImportOrderAdmin)    

class SourcedUnitInline(admin.TabularInline):
    model = SourcedUnit
    extra = 1
    readonly_fields = ["landed_cost_kes", "total_kes", "created_at"]
    fields = [
        "make", "model", "year", "chassis_number", "grade",
        "unit_price_usd", "freight_usd", "insurance_usd", "dollar_rate",
        "duty_kes", "clearing_kes", "service_fee_kes",
        "landed_cost_kes", "total_kes", "status",
    ]


class ImportRequestAdmin(admin.ModelAdmin):
    list_display = [
        "contact_name", "make", "model", "year", "status", "unit_count",
        "created_at",
    ]
    list_filter = ["status", "make"]
    search_fields = ["contact_name", "email", "phone", "make", "model"]
    readonly_fields = ["token", "created_at"]
    inlines = [SourcedUnitInline]

    @admin.display(description="Units")
    def unit_count(self, obj):
        return obj.units.count()


admin.site.register(ImportRequest, ImportRequestAdmin)
