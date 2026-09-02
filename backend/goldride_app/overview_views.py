"""The owner's view of the business: one screen, one request.

Every other staff screen answers "what do I do next". This one answers "how is
the company doing, and is anything stuck" - which no queue can, because the
interesting figures are sums across tables nobody has open at the same time.

Two rules shape what is in here:

Nothing is computed row by row in Python that the database can add up, because
this is one endpoint standing in for six screens and it is opened first thing
every morning. The one exception is sourcing capital, whose cost waterfall is a
chain of properties on SourcedUnit rather than columns - and that queryset is a
handful of rows.

And every money figure says which money it is. "Inventory value" is what the
stock is *listed at*, not what it cost us; "collected" is cash that arrived, not
sales booked. The names carry that, because a number on a dashboard gets quoted
later by somebody who was not in this conversation.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from cars.models import Car
from imports.models import ImportOrder, SourcedUnit
from payments.models import Payment
from tickets.models import Ticket

from .permissions import IsManager

User = get_user_model()

ZERO = Decimal("0.00")

# How far back the revenue chart looks by default, and the most it will look
# back however large the query string says. A year of columns is already at the
# limit of what fits on one axis without the labels colliding.
DEFAULT_MONTHS = 12
MAX_MONTHS = 36

# A listing this close to lapsing wants renewing now rather than after it has
# already dropped off the site. Mirrors the Inventory screen's worklist.
EXPIRING_SOON = timedelta(days=7)

# A ticket somebody claimed and then left alone. Claiming gates nothing, so an
# abandoned claim is invisible everywhere else in the dashboard.
STALE_CLAIM = timedelta(days=2)


def _money(value):
    """Decimals leave the API as strings, the same as every serializer here.

    Floats would be friendlier to the chart, but money is Decimal all the way
    through this project on purpose, and one payload that quietly stops being
    Decimal is how that decision gets lost.
    """
    return str((value or ZERO).quantize(Decimal("0.01")))


def _sum(queryset, field):
    total = queryset.aggregate(
        total=Coalesce(
            Sum(field),
            Value(ZERO),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]
    return total or ZERO


def _month_start(moment):
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _step_back(month, count):
    """`count` whole months before `month`, without a calendar library."""
    year, zero_based = divmod((month.year * 12 + month.month - 1) - count, 12)
    return month.replace(year=year, month=zero_based + 1)


def stock_figures():
    """What is on the site, and what it is listed at.

    `.live()` rather than a bare filter: expiry is evaluated on read, so a
    lapsed listing is already invisible to customers. A total that counted it
    would not match the Inventory screen, and the afternoon spent finding out
    why is the reason this is worth a sentence.
    """
    live = Car.objects.live()
    available = live.filter(availability="available")
    reserved = live.filter(availability="reserved")

    # No main image and nothing in the gallery. This is the photograph backlog
    # in one number - it was 30 of 49 cars when anyone last counted by hand.
    no_photo = (
        live.annotate(gallery=Count("images"))
        .filter(Q(image="") | Q(image__isnull=True), gallery=0)
        .count()
    )

    return {
        "available_count": available.count(),
        "available_value": _money(_sum(available, "price")),
        "reserved_count": reserved.count(),
        "reserved_value": _money(_sum(reserved, "price")),
        "sold_count": Car.objects.filter(availability="sold").count(),
        "without_photo": no_photo,
        "expiring_soon": live.filter(
            expires_at__isnull=False,
            expires_at__lte=timezone.now() + EXPIRING_SOON,
        ).count(),
    }


def sourcing_capital():
    """Money committed to units that are chosen but not yet stock.

    Python, not SQL: landed cost is a chain of properties over a dozen inputs
    and a pinned dollar rate, deliberately derived so an old quote can be read
    back. There are never many selected-and-unpushed units at once.
    """
    units = SourcedUnit.objects.filter(status="selected", pushed_to_car__isnull=True)
    total = sum((unit.landed_cost_kes for unit in units), ZERO)
    return {"unit_count": units.count(), "capital": _money(total)}


def collections(months):
    """Cash in, by month, split by how it arrived.

    Grouped on `paid_at`, which is stamped once and never moves. Grouping on
    updated_at would let a reconcile run drag an old payment into this month.

    Every month in the window is returned, including the empty ones. An axis
    that starts at the first payment hides how new the business is, and a gap
    in trade is itself a fact worth seeing.

    The method split is not decoration: Paystack refuses large amounts and
    M-PESA stops at 250,000, so the manual share is the share of the business
    that only closes by bank transfer.
    """
    now = timezone.now()
    this_month = _month_start(now)

    buckets = {}
    for index in range(months):
        start = _step_back(this_month, months - 1 - index)
        buckets[(start.year, start.month)] = {
            "month": start.strftime("%Y-%m"),
            "label": start.strftime("%b"),
            "year": start.year,
            "card": ZERO,
            "mpesa": ZERO,
            "manual": ZERO,
            "refunded": ZERO,
            "total": ZERO,
        }

    window_start = _step_back(this_month, months - 1)

    rows = (
        Payment.objects.filter(
            paid_at__gte=window_start, status__in=["paid", "refunded"]
        )
        .annotate(bucket=TruncMonth("paid_at"))
        .values("bucket", "status", "method")
        .annotate(total=Sum("amount"))
    )

    for row in rows:
        key = (row["bucket"].year, row["bucket"].month)
        bucket = buckets.get(key)
        if bucket is None:
            continue
        amount = row["total"] or ZERO
        # A refund keeps the paid_at of the payment it reverses, so it lands in
        # the month the money actually arrived rather than erasing that month.
        if row["status"] == "refunded":
            bucket["refunded"] += amount
        else:
            bucket[row["method"]] += amount
            bucket["total"] += amount

    series = [
        {
            "month": bucket["month"],
            "label": bucket["label"],
            "year": bucket["year"],
            "card": _money(bucket["card"]),
            "mpesa": _money(bucket["mpesa"]),
            "manual": _money(bucket["manual"]),
            "refunded": _money(bucket["refunded"]),
            "total": _money(bucket["total"]),
        }
        for bucket in buckets.values()
    ]

    current = Decimal(series[-1]["total"]) if series else ZERO
    previous = Decimal(series[-2]["total"]) if len(series) > 1 else ZERO

    # A percentage against nothing is not a percentage. Null, and the tile says
    # so in words rather than printing an infinity.
    if previous > 0:
        delta = round(float((current - previous) / previous * 100), 1)
    else:
        delta = None

    return {
        "this_month": _money(current),
        "last_month": _money(previous),
        "delta_percent": delta,
        "months": series,
    }


def receivables():
    """Billed against collected, over orders that are still live.

    Cancelled orders are excluded: their balance is owed by nobody, and leaving
    them in makes the outstanding figure grow every time a sale falls through -
    the one moment it should not.
    """
    orders = ImportOrder.objects.filter(cancelled_at__isnull=True)
    billed = _sum(orders, "total_amount")
    collected = _sum(
        Payment.objects.filter(status="paid", order__cancelled_at__isnull=True),
        "amount",
    )
    outstanding = billed - collected

    return {
        "billed": _money(billed),
        "collected": _money(collected),
        "outstanding": _money(outstanding if outstanding > ZERO else ZERO),
        "open_orders": orders.exclude(current_stage="delivered").count(),
        # Raised, but the customer has never been told how to pay it. The
        # difference between waiting on them and waiting on us.
        "awaiting_dispatch": Payment.objects.filter(
            status="pending", checkout_sent_at__isnull=True
        ).count(),
    }


def workload():
    """Where the queue is stuck.

    `unclaimed` and `stale_claims` are the two failure modes: nobody has picked
    it up, or somebody picked it up and stopped. The second has no home
    anywhere else in the dashboard, because claiming gates none of the work
    endpoints - so an abandoned claim looks exactly like work in progress.
    """
    now = timezone.now()
    open_tickets = Ticket.objects.exclude(status=Ticket.CLOSED)

    by_kind = {
        kind: open_tickets.filter(kind=kind).count()
        for kind, _label in Ticket.KIND_CHOICES
    }

    oldest = (
        open_tickets.order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )

    return {
        "open": open_tickets.count(),
        "unclaimed": open_tickets.filter(status=Ticket.OPEN).count(),
        "stale_claims": open_tickets.filter(
            status=Ticket.CLAIMED, claimed_at__lt=now - STALE_CLAIM
        ).count(),
        "by_kind": by_kind,
        "oldest_open_days": None if oldest is None else (now - oldest).days,
    }


def team_activity():
    """Who is on the dashboard, and what they have actually done.

    The same roster as /api/staff/team/, with the work attached. It reads as
    accountability rather than a staff list, which is the point: a manual
    payment is believed because a named person read a bank statement and said
    so, and a ticket is owned by whoever claimed it. Deactivated accounts stay
    listed - their name is on decisions, which is why removal deactivates
    rather than deletes.
    """
    people = (
        User.objects.filter(
            Q(groups__name__in=["Sales", "Manager"]) | Q(is_superuser=True)
        )
        .distinct()
        .annotate(
            tickets_claimed=Count(
                "tickets",
                filter=Q(tickets__status=Ticket.CLAIMED),
                distinct=True,
            ),
            tickets_closed=Count(
                "tickets",
                filter=Q(tickets__status=Ticket.CLOSED),
                distinct=True,
            ),
            payments_recorded=Count(
                "recorded_payments",
                filter=Q(recorded_payments__status="paid"),
                distinct=True,
            ),
        )
        .order_by("-is_active", "username")
        .prefetch_related("groups")
    )

    def role_of(person):
        if person.is_superuser:
            return "Owner"
        names = {group.name for group in person.groups.all()}
        return "Manager" if "Manager" in names else "Sales"

    return [
        {
            "id": person.id,
            "name": person.get_full_name() or person.username,
            "username": person.username,
            "role": role_of(person),
            "is_active": person.is_active,
            "tickets_claimed": person.tickets_claimed,
            "tickets_closed": person.tickets_closed,
            "payments_recorded": person.payments_recorded,
        }
        for person in people
    ]


class StaffOverviewView(APIView):
    """One request, because six requests would be six loading states."""

    permission_classes = [IsManager]

    @extend_schema(
        description="Business overview: stock value, cash collected by month, "
                    "receivables, queue health and per-person activity.",
        parameters=[
            OpenApiParameter(
                name="months",
                type=int,
                description=f"Months in the revenue series "
                            f"(default {DEFAULT_MONTHS}, max {MAX_MONTHS}).",
            )
        ],
        responses={200: dict},
    )
    def get(self, request):
        try:
            months = int(request.query_params.get("months", DEFAULT_MONTHS))
        except (TypeError, ValueError):
            months = DEFAULT_MONTHS
        months = max(1, min(months, MAX_MONTHS))

        return Response(
            {
                "generated_at": timezone.now(),
                "stock": stock_figures(),
                "sourcing": sourcing_capital(),
                "collections": collections(months),
                "receivables": receivables(),
                "work": workload(),
                "team": team_activity(),
            }
        )
