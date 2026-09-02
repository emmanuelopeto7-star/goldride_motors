"""Reconciliation that runs itself.

Until now the sweep only happened when somebody clicked, which meant a dropped
webhook - money taken and never recorded against an order - sat undiscovered
until a member of staff went looking. This runs it on a timer inside the
application, so it works the same in development, on a laptop and on whatever
host the site ends up on, with nothing to configure and no scheduler to forget.

Three things it has to get right:

**One sweep, not one per worker.** Every web worker starts this thread. Each
sweep opens a `ReconciliationRun` and claims it under a row lock with
`skip_locked`, so of four workers waking together, one sweeps and three see the
lock and go back to sleep rather than queueing behind it.

**Never take the process down.** It is a daemon thread that swallows everything:
a provider outage must not stop the site serving cars. Failures are recorded on
the run and logged.

**Stay out of the way of everything that is not a server.** `manage.py migrate`,
`test`, `shell` and `collectstatic` all import the app registry, and none of
them should quietly start talking to Paystack.
"""

import logging
import threading
import time

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

logger = logging.getLogger("goldride.payments")

_started = threading.Lock()
_running = False


def sweep(trigger, stale_minutes=None, limit=None):
    """Reconcile pending payments once. Returns the ReconciliationRun.

    Safe to call from anywhere - the command, a staff request, the timer. Only
    one runs at a time across every process sharing the database.
    """
    from .models import Payment, ReconciliationRun
    from .reconciliation import reconcile_payment

    if stale_minutes is None:
        stale_minutes = getattr(settings, "RECONCILE_STALE_MINUTES", 2)

    run = ReconciliationRun.objects.create(trigger=trigger)

    # The claim. Anything already sweeping holds its own row; skip_locked means
    # we find that out immediately instead of blocking until it finishes.
    with transaction.atomic():
        claimed = (
            ReconciliationRun.objects.select_for_update(skip_locked=True)
            .filter(pk=run.pk)
            .exists()
        )
        if not claimed:
            run.state = ReconciliationRun.DONE
            run.error = "another sweep holds the lock"
            run.finished_at = timezone.now()
            run.save(update_fields=["state", "error", "finished_at"])
            return run

        if _another_sweep_is_running(run):
            run.state = ReconciliationRun.DONE
            run.error = "another sweep was already running"
            run.finished_at = timezone.now()
            run.save(update_fields=["state", "error", "finished_at"])
            return run

        # Payments created seconds ago are still being paid in a browser tab.
        # ABANDONED_GRACE already protects a live card checkout from being
        # called failed; this just keeps the sweep from asking about something
        # nobody has had time to finish.
        cutoff = timezone.now() - timezone.timedelta(minutes=stale_minutes)
        pending = Payment.objects.filter(
            status="pending", created_at__lte=cutoff
        ).order_by("created_at")
        if limit:
            pending = pending[:limit]

        checked = updated = 0
        try:
            for payment in list(pending):
                changed, _message = reconcile_payment(payment)
                checked += 1
                updated += 1 if changed else 0
        except Exception as problem:  # noqa: BLE001 - see the module docstring
            run.state = ReconciliationRun.FAILED
            run.error = str(problem)[:300]
            logger.exception("reconciliation sweep failed")
        else:
            run.state = ReconciliationRun.DONE

        run.checked = checked
        run.updated = updated
        run.finished_at = timezone.now()
        run.save(
            update_fields=["state", "error", "checked", "updated", "finished_at"]
        )

    if run.updated:
        logger.info(
            "reconciliation updated %s of %s pending payments",
            run.updated,
            run.checked,
        )
    return run


def _another_sweep_is_running(run):
    """True if a sweep started recently and never finished.

    The row lock covers processes running right now; this covers the process
    that was killed mid-sweep and left its row open. Anything still `running`
    after twice the interval is assumed dead, not busy.
    """
    from .models import ReconciliationRun

    minutes = max(getattr(settings, "RECONCILE_INTERVAL_MINUTES", 30), 1)
    since = timezone.now() - timezone.timedelta(minutes=minutes * 2)

    return (
        ReconciliationRun.objects.filter(
            state=ReconciliationRun.RUNNING, started_at__gte=since
        )
        .exclude(pk=run.pk)
        .exists()
    )


def _loop(interval_seconds):
    # A moment before the first sweep: workers start together, and all of them
    # hitting the database in the same instant to discover they are not the one
    # that gets to sweep is a poor way to begin serving traffic.
    time.sleep(min(interval_seconds, 60))

    while True:
        try:
            sweep(trigger="automatic")
        except Exception:  # noqa: BLE001
            # sweep() records its own failures; this is the belt for anything
            # it could not, such as the database being away entirely.
            logger.exception("reconciliation thread caught an error")
        time.sleep(interval_seconds)


def start():
    """Begin the timer, unless this process has no business running one."""
    global _running

    minutes = getattr(settings, "RECONCILE_INTERVAL_MINUTES", 30)
    if not minutes:
        logger.info("automatic reconciliation is switched off")
        return False

    # In-memory SQLite is the test database; a background thread reconciling
    # against it would race every test in the suite.
    if connection.settings_dict.get("NAME") in (":memory:",):
        return False

    with _started:
        if _running:
            return False
        _running = True

    thread = threading.Thread(
        target=_loop,
        args=(minutes * 60,),
        name="goldride-reconcile",
        daemon=True,
    )
    thread.start()
    logger.info("automatic reconciliation every %s minutes", minutes)
    return True
