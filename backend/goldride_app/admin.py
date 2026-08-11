from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """The only way to mark an address proved without a provider saying so.

    Accounts that predate this model were all backfilled as unverified, so a
    social sign-in on one of their addresses is refused until somebody who
    can check the address ticks the box here.
    """

    list_display = ["user", "user_email", "email_verified", "created_at"]
    list_filter = ["email_verified"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["user", "created_at"]

    @admin.display(description="email", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email or "-"
