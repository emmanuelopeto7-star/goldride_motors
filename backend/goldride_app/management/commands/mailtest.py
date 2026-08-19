"""Prove an email actually leaves the building.

The console backend succeeds at everything, so "no error" has never meant
"delivered". This says which backend is in use, sends one real message, and
reports what happened - run it against production settings after wiring SMTP
and before believing any of the notifications work.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from goldride_app.mail import send


class Command(BaseCommand):
    help = "Send one test email and report whether it was delivered"

    def add_arguments(self, parser):
        parser.add_argument("to", help="Address to send the test to")

    def handle(self, *args, **options):
        recipient = options["to"]
        console = "console" in settings.EMAIL_BACKEND

        self.stdout.write(f"backend : {settings.EMAIL_BACKEND}")
        self.stdout.write(f"host    : {settings.EMAIL_HOST or '(none)'}:{settings.EMAIL_PORT}")
        self.stdout.write(f"from    : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"to      : {recipient}")
        self.stdout.write("")

        if console:
            self.stdout.write(
                self.style.WARNING(
                    "This is the console backend. The message below is printed, "
                    "not sent - nobody receives it. Set EMAIL_BACKEND to "
                    "django.core.mail.backends.smtp.EmailBackend to send for real."
                )
            )
            self.stdout.write("")

        ok = send(
            subject="Goldride Motors - test message",
            message=(
                "If you are reading this in an inbox, outbound email works.\n\n"
                "Sent by manage.py mailtest."
            ),
            to=recipient,
        )

        self.stdout.write("")
        if ok and not console:
            self.stdout.write(self.style.SUCCESS(f"Accepted by the mail server for {recipient}."))
            self.stdout.write("Check the inbox - accepted is not the same as delivered.")
        elif ok:
            self.stdout.write(self.style.WARNING("Printed to the console. Nothing was sent."))
        else:
            self.stdout.write(self.style.ERROR("Failed. The reason is in the log above."))
