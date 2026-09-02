from django.apps import AppConfig


class DealersConfig(AppConfig):
    name = 'dealers'

    def ready(self):
        # Raises the staff ticket for every application, and closes it on the
        # decision. Same shape as the other three ticket kinds.
        from . import signals  # noqa: F401
