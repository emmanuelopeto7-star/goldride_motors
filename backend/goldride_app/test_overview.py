"""The business overview endpoint.

The tests worth having here are not "does it return 200". They are the three
ways a dashboard lies: money grouped on a timestamp that moves, a total that
counts rows the rest of the site has already hidden, and a percentage against
zero. Each has a test that fails if the guard is removed.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from cars.models import Car
from imports.models import ImportOrder
from inquiries.models import Inquiry
from payments.models import Payment
from tickets.models import Ticket

User = get_user_model()
URL = "/api/staff/overview/"


def staff(username, role):
    user = User.objects.create_user(username, f"{username}@goldride.co.ke", "pw")
    Group.objects.get_or_create(name=role)[0].user_set.add(user)
    return user


def a_car(**overrides):
    fields = {
        "make": "Toyota",
        "model": "Land Cruiser",
        "year": 2019,
        "price": Decimal("5000000.00"),
        "description": "seeded",
    }
    fields.update(overrides)
    return Car.objects.create(**fields)


def an_order(total="1000000.00"):
    return ImportOrder.objects.create(
        customer_name="Wanjiru",
        phone="0700000000",
        car_description="2019 Toyota Land Cruiser",
        total_amount=Decimal(total),
    )


def an_enquiry(car=None):
    """An enquiry, and the ticket its signal raises.

    Tickets are built through their subject rather than directly: a check
    constraint requires the kind and the subject column to agree, and going the
    long way round also exercises the signal that raises them in production.
    """
    inquiry = Inquiry.objects.create(
        car=car or a_car(),
        name="Wanjiru",
        phone="0700000000",
        email="wanjiru@example.com",
        message="Is this still available?",
    )
    return inquiry.ticket


def a_payment(order, amount="500000.00", method="card", status="pending"):
    return Payment.objects.create(
        order=order, amount=Decimal(amount), method=method, status=status
    )


class OverviewAccessTests(APITestCase):
    def test_sales_cannot_see_the_business_figures(self):
        """Sales works the queue. Revenue and receivables are not theirs."""
        user = staff("asha", "Sales")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_signed_out_is_refused(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    def test_a_manager_gets_the_overview(self):
        user = staff("boss", "Manager")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        for section in ("stock", "collections", "receivables", "work", "team"):
            self.assertIn(section, response.data)


class OverviewFiguresTests(APITestCase):
    def setUp(self):
        self.boss = staff("boss", "Manager")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.boss).key}"
        )

    def get(self, **params):
        return self.client.get(URL, params).data

    # --- stock ----------------------------------------------------------

    def test_inventory_value_counts_only_available_stock(self):
        a_car(price="4000000.00")
        a_car(price="6000000.00")
        a_car(price="9000000.00", availability="reserved")
        a_car(price="7000000.00", availability="sold")

        stock = self.get()["stock"]
        self.assertEqual(stock["available_count"], 2)
        self.assertEqual(Decimal(stock["available_value"]), Decimal("10000000.00"))
        self.assertEqual(Decimal(stock["reserved_value"]), Decimal("9000000.00"))
        self.assertEqual(stock["sold_count"], 1)

    def test_an_expired_listing_is_not_counted_as_stock(self):
        """It is already invisible to customers, so it is not inventory.

        Without this the tile disagrees with the Inventory screen, which
        filters the same way.
        """
        a_car(price="4000000.00")
        a_car(price="8000000.00", expires_at=timezone.now() - timedelta(days=1))

        stock = self.get()["stock"]
        self.assertEqual(stock["available_count"], 1)
        self.assertEqual(Decimal(stock["available_value"]), Decimal("4000000.00"))

    def test_cars_with_no_photograph_are_counted(self):
        a_car()
        a_car(image="cars/prado.jpg")

        self.assertEqual(self.get()["stock"]["without_photo"], 1)

    # --- collections ----------------------------------------------------

    def test_collections_are_grouped_by_when_the_money_arrived(self):
        order = an_order()
        old = a_payment(order, "300000.00", status="paid")
        Payment.objects.filter(pk=old.pk).update(
            paid_at=timezone.now() - timedelta(days=70)
        )
        a_payment(order, "200000.00", status="paid")

        months = self.get()["collections"]["months"]
        self.assertEqual(Decimal(months[-1]["total"]), Decimal("200000.00"))
        self.assertEqual(Decimal(months[-3]["total"]), Decimal("300000.00"))

    def test_touching_an_old_payment_does_not_move_its_month(self):
        """The whole reason paid_at exists.

        Grouped on updated_at, a reconcile run or an edited note would drag an
        old payment into the current month and the chart would rewrite its own
        history every time the job ran.
        """
        order = an_order()
        payment = a_payment(order, "300000.00", status="paid")
        two_months_ago = timezone.now() - timedelta(days=70)
        Payment.objects.filter(pk=payment.pk).update(paid_at=two_months_ago)

        payment.refresh_from_db()
        payment.note = "reconciled by the nightly job"
        payment.save()

        months = self.get()["collections"]["months"]
        self.assertEqual(Decimal(months[-1]["total"]), Decimal("0.00"))
        self.assertEqual(Decimal(months[-3]["total"]), Decimal("300000.00"))

    def test_paid_at_is_stamped_once_and_never_moves(self):
        order = an_order()
        payment = a_payment(order)
        self.assertIsNone(payment.paid_at)

        payment.status = "paid"
        payment.save()
        first = payment.paid_at
        self.assertIsNotNone(first)

        payment.note = "queried by the customer"
        payment.save()
        payment.refresh_from_db()
        self.assertEqual(payment.paid_at, first)

    def test_paid_at_survives_a_save_that_lists_its_fields(self):
        """update_fields names the columns the caller knows about.

        The record-by-hand view passes one, and paid_at would be dropped on the
        way to the database if save() did not add itself to the list.
        """
        order = an_order()
        payment = a_payment(order, method="manual")
        payment.status = "paid"
        payment.save(update_fields=["status", "updated_at"])

        payment.refresh_from_db()
        self.assertIsNotNone(payment.paid_at)

    def test_every_month_in_the_window_is_returned(self):
        """Including the empty ones - a gap in trade is a fact."""
        series = self.get(months=6)["collections"]["months"]
        self.assertEqual(len(series), 6)
        self.assertEqual([Decimal(m["total"]) for m in series], [Decimal("0.00")] * 6)

    def test_the_method_split_adds_up_to_the_month_total(self):
        order = an_order(total="900000.00")
        a_payment(order, "100000.00", method="card", status="paid")
        a_payment(order, "200000.00", method="mpesa", status="paid")
        a_payment(order, "600000.00", method="manual", status="paid")

        month = self.get()["collections"]["months"][-1]
        self.assertEqual(
            Decimal(month["card"]) + Decimal(month["mpesa"]) + Decimal(month["manual"]),
            Decimal(month["total"]),
        )
        self.assertEqual(Decimal(month["manual"]), Decimal("600000.00"))

    def test_a_refund_is_reported_beside_its_month_not_erased_from_it(self):
        order = an_order()
        refunded = a_payment(order, "150000.00", status="paid")
        refunded.status = "refunded"
        refunded.save()

        month = self.get()["collections"]["months"][-1]
        self.assertEqual(Decimal(month["refunded"]), Decimal("150000.00"))
        self.assertEqual(Decimal(month["total"]), Decimal("0.00"))

    def test_growth_against_a_month_with_no_trade_is_null_not_infinite(self):
        order = an_order()
        a_payment(order, "100000.00", status="paid")

        collections = self.get()["collections"]
        self.assertEqual(Decimal(collections["last_month"]), Decimal("0.00"))
        self.assertIsNone(collections["delta_percent"])

    def test_the_window_is_capped(self):
        self.assertEqual(len(self.get(months=500)["collections"]["months"]), 36)
        self.assertEqual(len(self.get(months="nonsense")["collections"]["months"]), 12)

    # --- receivables ----------------------------------------------------

    def test_outstanding_is_what_is_billed_less_what_arrived(self):
        order = an_order("1000000.00")
        a_payment(order, "400000.00", status="paid")
        a_payment(order, "100000.00", status="pending")

        money = self.get()["receivables"]
        self.assertEqual(Decimal(money["billed"]), Decimal("1000000.00"))
        self.assertEqual(Decimal(money["collected"]), Decimal("400000.00"))
        self.assertEqual(Decimal(money["outstanding"]), Decimal("600000.00"))

    def test_a_cancelled_order_is_not_owed_by_anybody(self):
        """Otherwise receivables grow every time a sale falls through."""
        live = an_order("1000000.00")
        a_payment(live, "200000.00", status="paid")

        dead = an_order("5000000.00")
        dead.cancelled_at = timezone.now()
        dead.save(update_fields=["cancelled_at"])

        money = self.get()["receivables"]
        self.assertEqual(Decimal(money["billed"]), Decimal("1000000.00"))
        self.assertEqual(Decimal(money["outstanding"]), Decimal("800000.00"))

    # --- work and team --------------------------------------------------

    def test_a_claim_left_alone_is_reported_as_stale(self):
        ticket = an_enquiry()
        Ticket.objects.filter(pk=ticket.pk).update(
            status=Ticket.CLAIMED,
            claimed_by=self.boss,
            claimed_at=timezone.now() - timedelta(days=5),
        )

        work = self.get()["work"]
        self.assertEqual(work["open"], 1)
        self.assertEqual(work["unclaimed"], 0)
        self.assertEqual(work["stale_claims"], 1)
        self.assertEqual(work["by_kind"][Ticket.ENQUIRY], 1)

    def test_the_team_carries_what_each_person_has_done(self):
        asha = staff("asha", "Sales")
        order = an_order()
        payment = a_payment(order, method="manual")
        payment.status = "paid"
        payment.recorded_by = asha
        payment.recorded_at = timezone.now()
        payment.save()

        Ticket.objects.filter(pk=an_enquiry().pk).update(
            status=Ticket.CLOSED, claimed_by=asha, closed_at=timezone.now()
        )

        team = {person["username"]: person for person in self.get()["team"]}
        self.assertEqual(team["asha"]["payments_recorded"], 1)
        self.assertEqual(team["asha"]["tickets_closed"], 1)
        self.assertEqual(team["asha"]["role"], "Sales")
        self.assertEqual(team["boss"]["role"], "Manager")

    def test_a_deactivated_colleague_stays_on_the_list(self):
        """Their name is on decisions. Removal deactivates, it does not delete."""
        gone = staff("gone", "Sales")
        gone.is_active = False
        gone.save()

        team = {person["username"]: person for person in self.get()["team"]}
        self.assertIn("gone", team)
        self.assertFalse(team["gone"]["is_active"])
