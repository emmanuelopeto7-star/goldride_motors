from django.conf import settings
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    """Give every account that predates the model a profile.

    email_verified stays False for all of them, including staff: nobody ever
    confirmed those addresses, and guessing True here would reopen exactly
    the linking hole this model was added to close. Anyone who needs it can
    be flipped by hand in the admin.
    """
    User = apps.get_model(settings.AUTH_USER_MODEL)
    UserProfile = apps.get_model("goldride_app", "UserProfile")

    have = set(UserProfile.objects.values_list("user_id", flat=True))
    UserProfile.objects.bulk_create(
        [
            UserProfile(user_id=pk, email_verified=False)
            for pk in User.objects.exclude(pk__in=have).values_list("pk", flat=True)
        ]
    )


def drop_profiles(apps, schema_editor):
    apps.get_model("goldride_app", "UserProfile").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("goldride_app", "0002_userprofile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, drop_profiles),
    ]
