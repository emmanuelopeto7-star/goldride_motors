from django.conf import settings
from django.db import models


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
