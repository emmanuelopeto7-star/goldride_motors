from django.contrib import admin

from .models import ImportOrder, ImportMilestone

class MilestoneInline(admin.TabularInline):
    model = ImportMilestone
    extra = 1
    readonly_fields = ['created_at', 'updated_at']

class ImportOrderAdmin(admin.ModelAdmin):
    list_display=["customer_name", "car_description", "current_stage", "created_at"]
    list_filter=["current_stage"]
    search_fields=["customer_name", "phone", "car_description"]
    inlines=[MilestoneInline]

admin.site.register(ImportOrder, ImportOrderAdmin)    