from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = 'chat'

    def ready(self):
        # Puts a customer's enquiry into the conversation it starts.
        from . import signals  # noqa: F401
