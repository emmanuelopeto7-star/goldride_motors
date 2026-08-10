from django.contrib import admin, messages

from .models import PurchaseRequest
from .services import approve_request, reject_request


@admin.action(description="Approve — create the order and send the payment")
def approve_selected(modeladmin, request, queryset):
    for purchase_request in queryset:
        payment, dispatched, detail = approve_request(
            purchase_request, reviewed_by=request.user
        )

        if payment is None:
            modeladmin.message_user(
                request, f"{purchase_request}: {detail}", messages.ERROR
            )
            continue

        if dispatched and payment.method == "card":
            modeladmin.message_user(
                request,
                f"{purchase_request}: approved. Checkout link: {detail}",
                messages.SUCCESS,
            )
        elif dispatched:
            modeladmin.message_user(
                request,
                f"{purchase_request}: approved. M-PESA prompt sent to {purchase_request.phone}.",
                messages.SUCCESS,
            )
        else:
            modeladmin.message_user(
                request,
                f"{purchase_request}: approved, but online payment failed "
                f"({detail}). Recorded as a bank transfer.",
                messages.WARNING,
            )


@admin.action(description="Reject")
def reject_selected(modeladmin, request, queryset):
    for purchase_request in queryset:
        ok, detail = reject_request(purchase_request, reviewed_by=request.user)
        level = messages.SUCCESS if ok else messages.ERROR
        modeladmin.message_user(request, f"{purchase_request}: {detail}", level)


class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = [
        "customer",
        "car",
        "preferred_method",
        "status",
        "reviewed_by",
        "created_at",
    ]
    list_filter = ["status", "preferred_method"]
    search_fields = ["customer__username", "car__make", "car__model", "phone"]
    readonly_fields = ["status", "reviewed_by", "reviewed_at", "order", "created_at"]
    actions = [approve_selected, reject_selected]


admin.site.register(PurchaseRequest, PurchaseRequestAdmin)
