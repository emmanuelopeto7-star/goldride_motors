from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Whatever we know about an account that Django's User does not hold.

    Right now that is one thing: whether anybody ever proved the address on
    the account belongs to them. Registration cannot prove it, so a fresh
    account starts False and only a provider that vouches for the address
    (or, later, a confirmation link) may set it True.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        state = "verified" if self.email_verified else "unverified"
        return f"{self.user} ({state})"


def get_profile(user):
    """The profile for a user, creating it if some path missed the signal."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


class SocialAccount(models.Model):
    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("linkedin", "LinkedIn"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    uid = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "uid"], name="unique_provider_uid"
            )
        ]

    def __str__(self):
        return f"{self.user} via {self.get_provider_display()}"
