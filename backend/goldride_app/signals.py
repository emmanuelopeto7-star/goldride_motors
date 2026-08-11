from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """Every user has a profile, however the user was made.

    createsuperuser, the admin, a fixture and the API all end up here, so no
    code path has to remember - and email_verified defaults to False, which
    is the safe answer for all of them.
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
