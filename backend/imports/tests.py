"""Cancellation and re-engagement for import orders.

Doc gap 3.2 (MEDIUM): customers could always walk away, but nothing brought
them back - there was no cancelled state at all, and no way for staff to make
an offer against one.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from cars.models import Car

from .models import ImportOrder


def make_car(model="Prado", availability="available"):
    return Car.objects.create(
        make="Toyota",
        model=model,
        year=2019,
        price=Decimal("4250000.00"),
        description="A car.",
        availability=availability,
    )


class OrderCancellationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(
            "buyer", "buyer@example.com", "pw"
        )
        Group.objects.get_or_create(name="Customer")[0].user_set.add(self.customer)
        self.car = make_car()
        self.order = ImportOrder.objects.create(
            customer=self.customer,
            customer_name="Buyer",
            phone="+254700000000",
            car=self.car,
            car_description="Toyota Prado 2019",
            total_amount=Decimal("4250000.00"),
        )

    def as_customer(self):
        token = Token.objects.create(user=self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def as_sales(self):
        User = get_user_model()
        user = User.objects.create_user("sales", "sales@goldride.co.ke", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(user)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # --- cancelling ------------------------------------------------------

    def test_placing_an_order_reserves_the_car(self):
        self.car.refresh_from_db()
        self.assertEqual(self.car.availability, "reserved")

    def test_a_customer_can_cancel_their_own_order(self):
        self.as_customer()

        response = self.client.post(
            f"/api/my/orders/{self.order.pk}/cancel/",
            {"reason": "Found one locally"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_cancelled"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.cancel_reason, "Found one locally")

    def test_cancelling_puts_the_car_back_on_the_lot(self):
        self.as_customer()

        self.client.post(f"/api/my/orders/{self.order.pk}/cancel/")

        self.car.refresh_from_db()
        self.assertEqual(self.car.availability, "available")

    def test_cancelling_does_not_delete_the_order(self):
        """The cancelled order is the entire input to re-engagement."""
        self.as_customer()

        self.client.post(f"/api/my/orders/{self.order.pk}/cancel/")

        self.assertTrue(ImportOrder.objects.filter(pk=self.order.pk).exists())

    def test_cancelling_twice_is_refused(self):
        self.as_customer()
        self.client.post(f"/api/my/orders/{self.order.pk}/cancel/")

        response = self.client.post(f"/api/my/orders/{self.order.pk}/cancel/")

        self.assertEqual(response.status_code, 400)

    def test_a_delivered_order_cannot_be_cancelled(self):
        self.order.current_stage = "delivered"
        self.order.save()
        self.as_customer()

        response = self.client.post(f"/api/my/orders/{self.order.pk}/cancel/")

        self.assertEqual(response.status_code, 400)

    def test_someone_elses_order_404s_rather_than_403s(self):
        """A 403 would confirm the id exists."""
        User = get_user_model()
        stranger = User.objects.create_user("stranger", "s@example.com", "pw")
        Group.objects.get(name="Customer").user_set.add(stranger)
        token = Token.objects.create(user=stranger)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post(f"/api/my/orders/{self.order.pk}/cancel/")

        self.assertEqual(response.status_code, 404)

    def test_cancelling_requires_signing_in(self):
        response = self.client.post(f"/api/my/orders/{self.order.pk}/cancel/")

        self.assertIn(response.status_code, (401, 403))

    def test_sales_are_told_an_order_was_dropped(self):
        self.as_customer()
        mail.outbox.clear()

        self.client.post(f"/api/my/orders/{self.order.pk}/cancel/")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("cancelled", mail.outbox[0].subject.lower())

    def test_a_released_car_can_be_ordered_by_someone_else(self):
        """Releasing the car is the point of cancelling - it has to be orderable."""
        self.order.cancel(reason="changed my mind")

        second = ImportOrder(
            customer_name="Someone else",
            phone="+254711111111",
            car=self.car,
            car_description="Toyota Prado 2019",
        )
        second.full_clean()  # must not raise

    def test_editing_a_cancelled_order_does_not_re_reserve_its_car(self):
        self.order.cancel()

        self.order.phone = "+254722222222"
        self.order.save()

        self.car.refresh_from_db()
        self.assertEqual(self.car.availability, "available")

    # --- reactivation ----------------------------------------------------

    def test_staff_can_reactivate_a_cancelled_order(self):
        self.order.cancel(reason="too expensive")
        self.as_sales()

        response = self.client.post(
            f"/api/staff/orders/{self.order.pk}/reactivate/",
            {"message": "We can do 200,000 off if you still want it."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_cancelled"])
        self.assertIsNotNone(response.data["reactivated_at"])

    def test_reactivating_reserves_the_car_again(self):
        self.order.cancel()
        self.as_sales()

        self.client.post(
            f"/api/staff/orders/{self.order.pk}/reactivate/",
            {"message": "Still available."},
        )

        self.car.refresh_from_db()
        self.assertEqual(self.car.availability, "reserved")

    def test_the_customer_is_emailed_the_offer(self):
        self.order.cancel()
        self.as_sales()
        mail.outbox.clear()

        self.client.post(
            f"/api/staff/orders/{self.order.pk}/reactivate/",
            {"message": "200,000 off this week."},
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["buyer@example.com"])
        self.assertIn("200,000 off this week.", mail.outbox[0].body)

    def test_the_offer_email_carries_the_tracking_link(self):
        self.order.cancel()
        self.as_sales()
        mail.outbox.clear()

        self.client.post(
            f"/api/staff/orders/{self.order.pk}/reactivate/",
            {"message": "Back in stock."},
        )

        self.assertIn(str(self.order.token), mail.outbox[0].body)

    def test_reactivating_without_a_message_is_refused(self):
        """Reopening silently is not re-engagement."""
        self.order.cancel()
        self.as_sales()

        response = self.client.post(f"/api/staff/orders/{self.order.pk}/reactivate/")

        self.assertEqual(response.status_code, 400)

    def test_an_order_that_was_never_cancelled_cannot_be_reactivated(self):
        self.as_sales()

        response = self.client.post(
            f"/api/staff/orders/{self.order.pk}/reactivate/",
            {"message": "Hello again."},
        )

        self.assertEqual(response.status_code, 400)

    def test_reactivation_is_refused_once_the_car_has_been_sold(self):
        """Releasing the car means it really was available to someone else."""
        self.order.cancel()
        Car.objects.filter(pk=self.car.pk).update(availability="sold")
        self.as_sales()

        response = self.client.post(
            f"/api/staff/orders/{self.order.pk}/reactivate/",
            {"message": "Come back."},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("sold", response.data["error"])

    def test_reactivating_requires_staff(self):
        self.order.cancel()
        self.as_customer()

        response = self.client.post(
            f"/api/staff/orders/{self.order.pk}/reactivate/",
            {"message": "Let me back in."},
        )

        self.assertEqual(response.status_code, 403)

    def test_a_customer_with_no_address_is_reported_not_failed(self):
        """Still worth chasing by phone - the order must still reopen."""
        self.customer.email = ""
        self.customer.save(update_fields=["email"])
        self.order.cancel()
        self.as_sales()

        response = self.client.post(
            f"/api/staff/orders/{self.order.pk}/reactivate/",
            {"message": "Call me."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["emailed"])
        self.assertFalse(response.data["is_cancelled"])

    # --- worklists -------------------------------------------------------

    def test_staff_can_list_the_re_engagement_worklist(self):
        self.order.cancel()
        ImportOrder.objects.create(
            customer_name="Live one",
            phone="+254733333333",
            car_description="Mazda Demio 2018",
        )
        self.as_sales()

        response = self.client.get("/api/staff/orders/?cancelled=true")

        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.order.pk)

    def test_the_tracking_page_reports_a_cancelled_order(self):
        self.order.cancel(reason="personal reasons")

        response = self.client.get(f"/api/track/{self.order.token}/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_cancelled"])

    def test_the_tracking_page_does_not_leak_the_reason(self):
        """Anyone holding the link can read that page."""
        self.order.cancel(reason="lost my job")

        response = self.client.get(f"/api/track/{self.order.token}/")

        self.assertNotIn("cancel_reason", response.data)
