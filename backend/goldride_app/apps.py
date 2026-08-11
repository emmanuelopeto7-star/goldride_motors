from django.apps import AppConfig


class GoldrideAppConfig(AppConfig):
    name = 'goldride_app'

    def ready(self):
        # Registers the post_save hook that gives every user a profile.
        from . import signals  # noqa: F401
