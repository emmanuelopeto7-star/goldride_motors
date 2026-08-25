from django.contrib import admin

from .models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "status", "claimed_by", "created_at"]
    list_filter = ["kind", "status"]
    # Claiming is an act with a rule behind it - the conditional update in
    # Ticket.claim. The admin's plain save would write straight past it, so
    # ownership is read-only here and taken through the API.
    readonly_fields = ["claimed_by", "claimed_at", "closed_at", "created_at"]
