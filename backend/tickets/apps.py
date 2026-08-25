from django.apps import AppConfig


class TicketsConfig(AppConfig):
    name = 'tickets'

    def ready(self):
        # Registers the hooks that raise a ticket for every request that comes
        # in, and close it again when the request reaches a decision.
        from . import signals  # noqa: F401
