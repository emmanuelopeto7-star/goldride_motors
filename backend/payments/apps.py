import os
import sys

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = 'payments'

    def ready(self):
        """Start the reconciliation timer, in a server and nowhere else.

        An allowlist, not a blocklist. Every management command loads the app
        registry - `migrate`, `test`, `shell`, `check`, `collectstatic` - and a
        list of the ones to skip is a list somebody will add a command to and
        forget. Naming the two cases that *should* sweep leaves nothing to
        forget: a development server, and an ASGI or WSGI server where
        `manage.py` is not the entry point at all.

        runserver's autoreloader loads this twice; RUN_MAIN marks the real
        child, without which development runs two sweeps racing each other.
        """
        entry_point = os.path.basename(sys.argv[0] or "")

        if entry_point in ("manage.py", "django-admin", "django-admin.py"):
            command = sys.argv[1] if len(sys.argv) > 1 else ""
            if command != "runserver":
                return
            if os.environ.get("RUN_MAIN") != "true":
                return

        from .sweeper import start

        start()
