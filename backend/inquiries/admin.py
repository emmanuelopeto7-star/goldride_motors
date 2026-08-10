from django.contrib import admin
from .models import Inquiry
class InquiryAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "car", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "phone"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at"]
admin.site.register(Inquiry)

