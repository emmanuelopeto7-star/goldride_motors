"""Cancellation and re-engagement for import orders.

Doc gap 3.2 (MEDIUM): customers could always walk away, but nothing brought
them back - there was no cancelled state at all, and no way for staff to make
an offer against one.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

import tempfile

from cars.models import Car

# Uploads in tests must not land in the real media folder.
MEDIA_OVERRIDE = override_settings(MEDIA_ROOT=tempfile.mkdtemp())

from .models import ImportOrder, ImportRates, ImportRequest, SourcedUnit


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


def a_request(**overrides):
    fields = {
        "contact_name": "Amina Otieno",
        "email": "amina@example.com",
        "phone": "+254700111222",
        "make": "Toyota",
        "model": "Prado",
        "year": timezone.now().year - 5,
    }
    fields.update(overrides)
    return ImportRequest.objects.create(**fields)


def a_unit(request=None, **overrides):
    """A plausible Japanese import: USD 12,000 FOB, 1,500 freight, rate 130."""
    fields = {
        "request": request or a_request(),
        "make": "Toyota",
        "model": "Prado",
        "year": timezone.now().year - 5,
        "unit_price_usd": Decimal("12000.00"),
        "freight_usd": Decimal("1500.00"),
        "insurance_usd": Decimal("500.00"),
        "dollar_rate": Decimal("130.00"),
        "clearing_kes": Decimal("120000.00"),
        "service_fee_kes": Decimal("200000.00"),
    }
    fields.update(overrides)
    return SourcedUnit.objects.create(**fields)


class LandingCostTests(TestCase):
    """The arithmetic staff quote from. Wrong here means quoting at a loss."""

    def test_cnf_is_the_car_plus_freight(self):
        unit = a_unit()

        self.assertEqual(unit.cnf_usd, Decimal("13500.00"))

    def test_cif_adds_insurance_on_top_of_cnf(self):
        unit = a_unit()

        self.assertEqual(unit.cif_usd, Decimal("14000.00"))

    def test_the_dollar_rate_converts_the_whole_cnf(self):
        unit = a_unit()

        self.assertEqual(unit.cnf_kes, Decimal("1755000.00"))

    def test_each_kra_charge_is_worked_out_in_order(self):
        """They compound: excise sits on CIF plus duty, VAT on all three.
        Adding 25 + 25 + 16 to CIF would understate the bill badly."""
        unit = a_unit()  # CIF 14,000 USD x 130 = 1,820,000

        self.assertEqual(unit.import_duty_kes, Decimal("455000.00"))
        self.assertEqual(unit.excise_duty_kes, Decimal("568750.00"))
        self.assertEqual(unit.vat_kes, Decimal("455000.00"))
        self.assertEqual(unit.idf_kes, Decimal("63700.00"))
        self.assertEqual(unit.rdl_kes, Decimal("36400.00"))
        self.assertEqual(unit.taxes_kes, Decimal("1578850.00"))

    def test_compounding_is_not_the_same_as_summing_the_rates(self):
        """The mistake this arithmetic exists to avoid."""
        unit = a_unit()
        naive = unit.cif_kes * Decimal("71.5") / Decimal("100")

        self.assertGreater(unit.taxes_kes, naive)

    def test_a_bigger_engine_pays_more_excise_and_more_vat(self):
        """VAT sits on top of excise, so the band moves two figures, not one."""
        small = a_unit(excise_rate=Decimal("20"))
        large = a_unit(request=small.request, excise_rate=Decimal("35"))

        self.assertGreater(large.excise_duty_kes, small.excise_duty_kes)
        self.assertGreater(large.vat_kes, small.vat_kes)

    def test_landed_cost_is_cif_plus_taxes_plus_clearing(self):
        unit = a_unit()

        # 1,820,000 + 1,578,850 + 120,000
        self.assertEqual(unit.landed_cost_kes, Decimal("3518850.00"))

    def test_charges_are_assessed_on_crsp_when_kra_has_valued_it(self):
        """KRA assesses on its own depreciated valuation, not on what we paid.
        CIF is the estimate until an entry is lodged."""
        unit = a_unit(customs_value_kes=Decimal("2500000.00"))

        self.assertEqual(unit.customs_value, Decimal("2500000.00"))
        self.assertEqual(unit.import_duty_kes, Decimal("625000.00"))

    def test_cif_is_the_basis_until_kra_says_otherwise(self):
        unit = a_unit()

        self.assertEqual(unit.customs_value, unit.cif_kes)

    def test_the_customer_total_adds_our_commission(self):
        """Without the fee the total is our cost - a zero-margin quote."""
        unit = a_unit()

        self.assertEqual(unit.total_kes, Decimal("3718850.00"))
        self.assertEqual(unit.total_kes - unit.landed_cost_kes, Decimal("200000.00"))

    def test_a_pinned_rate_survives_the_rate_moving(self):
        """The reason the rate is a column and not a setting."""
        unit = a_unit(dollar_rate=Decimal("129.00"))
        quoted = unit.total_kes

        a_unit(request=unit.request, dollar_rate=Decimal("138.00"))
        unit.refresh_from_db()

        self.assertEqual(unit.total_kes, quoted)

    def test_taxes_are_charged_even_with_no_other_extras(self):
        """Freight and clearing are optional. KRA is not."""
        unit = a_unit(
            freight_usd=Decimal("0"),
            insurance_usd=Decimal("0"),
            clearing_kes=Decimal("0"),
            service_fee_kes=Decimal("0"),
        )

        self.assertGreater(unit.total_kes, unit.cif_kes)
        self.assertEqual(unit.total_kes, unit.cif_kes + unit.taxes_kes)


class ImportEligibilityTests(TestCase):
    """KEBS will not clear a vehicle 8 or more years old. Refusing at the
    quote stage costs nothing; finding out at Mombasa costs the unit."""

    def a_pending_request(self, year):
        return ImportRequest(
            contact_name="A",
            email="a@example.com",
            phone="+254700000000",
            make="Toyota",
            model="Prado",
            year=year,
        )

    def test_a_recent_year_is_accepted(self):
        self.a_pending_request(timezone.now().year - 3).full_clean()

    def test_the_oldest_permitted_year_is_accepted(self):
        """The boundary is the whole rule - off by one here is lost business."""
        oldest = timezone.now().year - settings.IMPORT_MAX_VEHICLE_AGE_YEARS

        self.a_pending_request(oldest).full_clean()

    def test_a_year_too_old_is_refused(self):
        oldest = timezone.now().year - settings.IMPORT_MAX_VEHICLE_AGE_YEARS

        with self.assertRaises(DjangoValidationError):
            self.a_pending_request(oldest - 1).full_clean()

    def test_a_future_year_is_refused(self):
        with self.assertRaises(DjangoValidationError):
            self.a_pending_request(timezone.now().year + 2).full_clean()

    def test_the_rule_applies_to_sourced_units_too(self):
        """A request can be in range while the unit found against it is not."""
        unit = SourcedUnit(
            request=a_request(),
            make="Toyota",
            model="Prado",
            year=timezone.now().year - settings.IMPORT_MAX_VEHICLE_AGE_YEARS - 1,
            unit_price_usd=Decimal("9000"),
            dollar_rate=Decimal("130"),
        )

        with self.assertRaises(DjangoValidationError):
            unit.full_clean()


class UnitSelectionTests(APITestCase):
    def setUp(self):
        self.request = a_request()
        self.first = a_unit(request=self.request)
        self.second = a_unit(request=self.request, unit_price_usd=Decimal("15000"))

    def url(self, unit):
        return f"/api/imports/requests/{self.request.token}/units/{unit.pk}/decide/"

    def test_choosing_one_rejects_the_others(self):
        """Choosing is also declining. Leaving siblings on offer would let the
        customer select twice."""
        response = self.client.post(self.url(self.first), {"decision": "select"})

        self.assertEqual(response.status_code, 200)
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual(self.first.status, "selected")
        self.assertEqual(self.second.status, "rejected")

    def test_selecting_moves_the_request_to_agreed(self):
        self.client.post(self.url(self.first), {"decision": "select"})

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "agreed")

    def test_a_second_selection_is_refused(self):
        self.client.post(self.url(self.first), {"decision": "select"})

        response = self.client.post(self.url(self.second), {"decision": "select"})

        self.assertEqual(response.status_code, 400)

    def test_rejecting_one_leaves_the_others_alone(self):
        response = self.client.post(
            self.url(self.first),
            {"decision": "reject", "reason": "Too many miles"},
        )

        self.assertEqual(response.status_code, 200)
        self.second.refresh_from_db()
        self.assertEqual(self.second.status, "offered")
        self.first.refresh_from_db()
        self.assertEqual(self.first.rejected_reason, "Too many miles")

    def test_a_selected_unit_cannot_then_be_rejected(self):
        self.client.post(self.url(self.first), {"decision": "select"})

        response = self.client.post(self.url(self.first), {"decision": "reject"})

        self.assertEqual(response.status_code, 400)

    def test_a_unit_from_another_request_is_not_reachable(self):
        """The token is the credential, so it has to actually be checked."""
        other = a_unit()
        url = f"/api/imports/requests/{self.request.token}/units/{other.pk}/decide/"

        response = self.client.post(url, {"decision": "select"})

        self.assertEqual(response.status_code, 404)

    def test_nonsense_decisions_are_refused(self):
        response = self.client.post(self.url(self.first), {"decision": "maybe"})

        self.assertEqual(response.status_code, 400)

    def test_the_itemised_quote_adds_up_to_its_own_total(self):
        """The one error a customer checking the arithmetic is guaranteed to
        find. Leading with C&F instead of CIF leaves the lines short by the
        insurance, which makes the whole breakdown look like a trick."""
        response = self.client.get(f"/api/imports/requests/{self.request.token}/")

        unit = response.data["units"][0]
        lines = [
            unit["cif_kes"], unit["import_duty_kes"], unit["excise_duty_kes"],
            unit["vat_kes"], unit["idf_kes"], unit["rdl_kes"],
            unit["clearing_kes"], unit["service_fee_kes"],
        ]

        self.assertEqual(sum(Decimal(line) for line in lines),
                         Decimal(unit["total_kes"]))

    def test_the_customer_is_not_shown_what_we_paid(self):
        """A quote is a price, not an invitation to audit the margin."""
        response = self.client.get(f"/api/imports/requests/{self.request.token}/")

        unit = response.data["units"][0]
        self.assertNotIn("unit_price_usd", unit)
        self.assertNotIn("landed_cost_kes", unit)
        self.assertIn("total_kes", unit)


class ImportRequestFlowTests(APITestCase):
    URL = "/api/imports/requests/"

    def payload(self, **overrides):
        fields = {
            "contact_name": "Amina Otieno",
            "email": "amina@example.com",
            "phone": "+254700111222",
            "make": "Toyota",
            "model": "Prado",
            "year": timezone.now().year - 5,
        }
        fields.update(overrides)
        return fields

    def test_a_guest_can_raise_a_request(self):
        """A registration wall in front of a lead loses the lead."""
        response = self.client.post(self.URL, self.payload())

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(ImportRequest.objects.get().customer)

    def test_the_response_carries_the_token_to_come_back_with(self):
        response = self.client.post(self.URL, self.payload())

        self.assertTrue(response.data["token"])

    def test_an_ineligible_year_is_refused_at_submission(self):
        too_old = timezone.now().year - settings.IMPORT_MAX_VEHICLE_AGE_YEARS - 1

        response = self.client.post(self.URL, self.payload(year=too_old))

        self.assertEqual(response.status_code, 400)
        self.assertIn("year", response.data)

    def test_both_the_customer_and_sales_are_emailed(self):
        mail.outbox.clear()

        self.client.post(self.URL, self.payload())

        recipients = [m.to[0] for m in mail.outbox]
        self.assertIn("amina@example.com", recipients)
        self.assertIn("sales@goldridemotors.co.ke", recipients)

    def test_a_signed_in_customer_is_attached_to_the_request(self):
        User = get_user_model()
        user = User.objects.create_user("amina", "amina@example.com", "pw")
        Group.objects.get_or_create(name="Customer")[0].user_set.add(user)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.client.post(self.URL, self.payload())

        self.assertEqual(ImportRequest.objects.get().customer, user)

    def test_tracking_is_public_and_shows_the_units(self):
        request = a_request()
        a_unit(request=request)

        response = self.client.get(f"/api/imports/requests/{request.token}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["units"]), 1)


class StaffSourcingTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user("sourcer", "s@goldride.co.ke", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(user)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.request = a_request()

    def test_adding_the_first_unit_moves_the_request_to_sourcing(self):
        """The status should follow from the work, not need remembering."""
        response = self.client.post("/api/staff/sourced-units/", {
            "request": self.request.pk,
            "make": "Toyota",
            "model": "Prado",
            "year": timezone.now().year - 4,
            "unit_price_usd": "12000.00",
            "dollar_rate": "130.00",
        })

        self.assertEqual(response.status_code, 201)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "sourcing")

    def test_staff_see_the_whole_waterfall(self):
        a_unit(request=self.request)

        response = self.client.get("/api/staff/sourced-units/")

        unit = response.data["results"][0]
        for field in ("cnf_usd", "cif_usd", "cnf_kes", "landed_cost_kes", "total_kes"):
            self.assertIn(field, unit)

    def test_notifying_hands_the_choice_to_the_customer(self):
        a_unit(request=self.request)
        mail.outbox.clear()

        response = self.client.post(
            f"/api/staff/import-requests/{self.request.pk}/notify/"
        )

        self.assertEqual(response.status_code, 200)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "awaiting_selection")
        self.assertEqual(mail.outbox[0].to, ["amina@example.com"])

    def test_notifying_with_nothing_on_offer_is_refused(self):
        """An email promising options that do not exist is worse than none."""
        response = self.client.post(
            f"/api/staff/import-requests/{self.request.pk}/notify/"
        )

        self.assertEqual(response.status_code, 400)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "pending")

    def test_sourcing_requires_staff(self):
        self.client.credentials()

        response = self.client.get("/api/staff/sourced-units/")

        self.assertIn(response.status_code, (401, 403))


@MEDIA_OVERRIDE
class PushToStockTests(APITestCase):
    """Doc §4, the flywheel.

    A rejected unit has already been found, graded and costed. Discarding it
    throws away work that was paid for in staff time; converting it turns that
    work into inventory.
    """

    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user("sourcer", "s@goldride.co.ke", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(user)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.request = a_request()
        self.unit = a_unit(
            request=self.request,
            chassis_number="TRJ150-0012345",
            mileage_km=68000,
            grade="4.5",
            exterior_colour="Pearl White",
        )
        self.unit.reject("Wanted a different colour")

    def url(self, unit=None):
        return f"/api/staff/sourced-units/{(unit or self.unit).pk}/push-to-stock/"

    # --- pricing ---------------------------------------------------------

    def test_the_price_is_landed_cost_plus_the_default_markup(self):
        # landed cost 3,518,850 x 1.15 = 4,046,677.50, rounded up
        self.assertEqual(self.unit.stock_price(), Decimal("4047000"))

    def test_pricing_ignores_the_commission_from_the_original_quote(self):
        """Charging it twice prices the car out of its own market."""
        priced_off_total = self.unit.total_kes * Decimal("1.15")

        self.assertLess(self.unit.stock_price(), priced_off_total)

    def test_a_markup_can_be_given_per_unit(self):
        # 3,518,850 x 1.25 = 4,398,562.50, rounded up
        self.assertEqual(self.unit.stock_price(Decimal("25")), Decimal("4399000"))

    def test_the_price_is_rounded_up_to_a_round_thousand(self):
        """Nobody lists a car at 3,041,732, and rounding down erodes margin."""
        unit = a_unit(request=self.request, clearing_kes=Decimal("120333.00"))

        price = unit.stock_price()

        self.assertEqual(price % Decimal("1000"), 0)
        self.assertGreaterEqual(price, unit.landed_cost_kes)

    # --- the conversion --------------------------------------------------

    def test_pushing_creates_an_available_listing(self):
        response = self.client.post(self.url())

        self.assertEqual(response.status_code, 201)
        car = Car.objects.get(pk=response.data["id"])
        self.assertEqual(car.availability, "available")
        self.assertEqual(car.make, "Toyota")
        self.assertEqual(car.year, self.unit.year)

    def test_the_listing_carries_the_specs_that_were_known(self):
        self.client.post(self.url())

        car = Car.objects.get()
        self.assertEqual(car.mileage_km, 68000)
        self.assertEqual(car.exterior_colour, "Pearl White")

    def test_the_chassis_becomes_the_listing_vin(self):
        self.client.post(self.url())

        self.assertEqual(Car.objects.get().vin, "TRJ150-0012345")

    def test_a_chassis_too_long_for_the_vin_column_is_kept_as_a_reference(self):
        """17 characters is a VIN. Japanese chassis numbers are not always one,
        and losing the traceability would be worse than an empty vin."""
        unit = a_unit(
            request=self.request,
            chassis_number="A-VERY-LONG-CHASSIS-NUMBER-9999",
        )
        unit.reject()

        self.client.post(self.url(unit))

        car = Car.objects.get()
        self.assertEqual(car.vin, "")
        self.assertIn("A-VERY-LONG-CHASSIS", car.reference)

    def test_the_description_is_written_from_what_we_know(self):
        self.client.post(self.url())

        description = Car.objects.get().description
        self.assertIn("Toyota", description)
        self.assertIn("4.5", description)
        self.assertIn("68,000 km", description)

    def test_the_unit_records_where_it_went(self):
        response = self.client.post(self.url())

        self.unit.refresh_from_db()
        self.assertEqual(self.unit.pushed_to_car_id, response.data["id"])
        self.assertIsNotNone(self.unit.pushed_at)

    def test_the_photo_is_copied_not_shared(self):
        """Deleting the sourcing record must not blank the listing."""
        unit = a_unit(request=self.request)
        unit.photo = SimpleUploadedFile("unit.jpg", b"not-a-real-jpeg")
        unit.save(update_fields=["photo"])
        unit.reject()

        self.client.post(self.url(unit))

        car = Car.objects.get()
        self.assertTrue(car.image)
        self.assertNotEqual(car.image.name, unit.photo.name)

    # --- the guards ------------------------------------------------------

    def test_a_unit_cannot_be_pushed_twice(self):
        """The car physically exists once."""
        self.client.post(self.url())

        response = self.client.post(self.url())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Car.objects.count(), 1)

    def test_a_selected_unit_cannot_be_pushed(self):
        """It belongs to the customer who chose it."""
        unit = a_unit(request=a_request())
        unit.select()

        response = self.client.post(self.url(unit))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Car.objects.count(), 0)

    def test_a_chassis_already_on_the_lot_is_refused(self):
        """Exactly the duplicate the VIN constraint exists to prevent - and it
        would otherwise surface as a 500 from the database."""
        Car.objects.create(
            make="Toyota", model="Prado", year=2020,
            price=Decimal("3000000"), description="Already here.",
            vin="TRJ150-0012345",
        )

        response = self.client.post(self.url())

        self.assertEqual(response.status_code, 400)
        self.assertIn("chassis", response.data["error"])

    def test_a_negative_markup_is_refused(self):
        response = self.client.post(self.url(), {"markup_percent": "-10"})

        self.assertEqual(response.status_code, 400)

    def test_a_nonsense_markup_is_refused(self):
        response = self.client.post(self.url(), {"markup_percent": "cheap"})

        self.assertEqual(response.status_code, 400)

    def test_pushing_requires_staff(self):
        self.client.credentials()

        response = self.client.post(self.url())

        self.assertIn(response.status_code, (401, 403))

    def test_the_new_listing_is_live_on_the_public_site(self):
        """The whole point - it has to become sellable inventory."""
        self.client.post(self.url())
        self.client.credentials()

        response = self.client.get("/api/cars/")

        self.assertEqual(response.data["count"], 1)

    def test_staff_can_preview_the_price_before_converting(self):
        response = self.client.get("/api/staff/sourced-units/")

        unit = response.data["results"][0]
        self.assertIn("stock_price_preview", unit)


class PinnedRateTests(TestCase):
    """Rates became editable, which introduces the risk they were editable to
    avoid: a quote silently changing after it was sent."""

    def test_a_new_unit_takes_the_rates_in_force(self):
        ImportRates.objects.create(
            duty_rate=Decimal("30"), excise_rate=Decimal("35"),
            vat_rate=Decimal("18"), idf_rate=Decimal("3"),
            rdl_rate=Decimal("1.5"), stock_markup=Decimal("20"),
        )

        unit = a_unit(excise_rate=None)

        self.assertEqual(unit.duty_rate, Decimal("30"))
        self.assertEqual(unit.vat_rate, Decimal("18"))
        self.assertEqual(unit.excise_rate, Decimal("35"))

    def test_an_old_quote_does_not_move_when_the_rates_do(self):
        """The whole reason the rates are copied onto the row."""
        unit = a_unit()
        quoted = unit.total_kes

        ImportRates.objects.create(
            duty_rate=Decimal("40"), excise_rate=Decimal("40"),
            vat_rate=Decimal("20"), idf_rate=Decimal("5"),
            rdl_rate=Decimal("4"), effective_from=timezone.now().date(),
        )
        unit.refresh_from_db()

        self.assertEqual(unit.total_kes, quoted)

    def test_editing_a_unit_does_not_re_rate_it(self):
        unit = a_unit()
        quoted = unit.total_kes
        ImportRates.objects.create(duty_rate=Decimal("40"))

        unit.clearing_kes = unit.clearing_kes
        unit.save()

        self.assertEqual(unit.total_kes, quoted)

    def test_an_excise_band_set_by_hand_is_not_overwritten(self):
        ImportRates.objects.create(excise_rate=Decimal("25"))

        unit = a_unit(excise_rate=Decimal("35"))

        self.assertEqual(unit.excise_rate, Decimal("35"))

    def test_rates_fall_back_to_settings_when_the_table_is_empty(self):
        """The migration seeds a row, so this is the belt-and-braces path -
        a database restored without it must still quote rather than crash."""
        ImportRates.objects.all().delete()

        rates = ImportRates.current()

        self.assertEqual(rates.duty_rate, settings.IMPORT_DUTY_RATE)
        self.assertIsNone(rates.pk)

    def test_the_migration_leaves_a_row_to_edit(self):
        """An empty table and an invisible settings fallback is a bad first
        experience for whoever has to change a rate."""
        self.assertTrue(ImportRates.objects.exists())

    def test_future_dated_rates_are_not_used_yet(self):
        """Budget changes are announced before they take effect."""
        ImportRates.objects.create(
            duty_rate=Decimal("30"),
            effective_from=timezone.now().date() + timedelta(days=30),
        )

        self.assertEqual(ImportRates.current().duty_rate, settings.IMPORT_DUTY_RATE)

    def test_the_stock_markup_comes_from_the_table_too(self):
        ImportRates.objects.create(stock_markup=Decimal("30"))
        unit = a_unit()

        # landed 3,518,850 x 1.30 = 4,574,505, rounded up
        self.assertEqual(unit.stock_price(), Decimal("4575000"))


class ImportRatesEndpointTests(APITestCase):
    def as_sales(self):
        User = get_user_model()
        user = User.objects.create_user("rates", "r@goldride.co.ke", "pw")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(user)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_staff_are_served_the_live_rates(self):
        """The sourcing screen previews totals with these, so a stale copy
        baked into the JS bundle would quote the wrong number."""
        ImportRates.objects.create(duty_rate=Decimal("30"), vat_rate=Decimal("18"))
        self.as_sales()

        response = self.client.get("/api/staff/import-rates/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data["duty"]), Decimal("30"))
        self.assertEqual(Decimal(response.data["vat"]), Decimal("18"))

    def test_the_rates_are_not_public(self):
        response = self.client.get("/api/staff/import-rates/")

        self.assertIn(response.status_code, (401, 403))
