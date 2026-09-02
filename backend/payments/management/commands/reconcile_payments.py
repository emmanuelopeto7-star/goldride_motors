"""Reconcile pending payments once, from the shell or an external scheduler.

The application sweeps on its own every RECONCILE_INTERVAL_MINUTES. This is the
same work, for a host where you would rather drive it from cron - set
RECONCILE_INTERVAL_MINUTES=0 in that case so the two do not both run - or for
looking at what a sweep would do right now.
"""

from django.core.management.base import BaseCommand

from payments.models import ReconciliationRun
from payments.sweeper import sweep


class Command(BaseCommand):
    help = "Ask each provider what happened to every pending payment"

    def add_arguments(self, parser):
        parser.add_argument(
            "--stale-minutes",
            type=int,
            default=None,
            help="Ignore payments raised more recently than this. Defaults to "
                 "RECONCILE_STALE_MINUTES; 0 checks everything pending.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Check at most this many, oldest first.",
        )

    def handle(self, *args, **options):
        run = sweep(
            trigger=ReconciliationRun.COMMAND,
            stale_minutes=options["stale_minutes"],
            limit=options["limit"],
        )

        if run.state == ReconciliationRun.FAILED:
            self.stderr.write(self.style.ERROR(f"failed: {run.error}"))
            return

        if run.error:
            # Not a failure - it declined to run because another sweep held the
            # lock, which is the mechanism working.
            self.stdout.write(run.error)
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"checked {run.checked}, updated {run.updated}, "
                f"in {run.seconds}s"
            )
        )
