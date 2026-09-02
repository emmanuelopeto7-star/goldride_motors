"""Dealers listing their cars with us.

The tests worth having are the ones guarding a promise that would be expensive
to break: nothing a dealer submits reaches the public site before somebody here
approves it; one application produces one account however many managers click;
an invitation link cannot be reused; and a dealer can never see, edit or file
anything under another dealership.
"""

import tempfile
from decimal import Decimal
from io import BytesIO

from PIL import Image

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail, signing
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from cars.models import Car
from tickets.models import Ticket

from .activation import ActivationError, make_token, read_token
from .models import Dealer, DealerApplication, DealerDocument, DealerListing
from .services import approve_application, approve_listing

User = get_user_model()

APPLY = "/api/dealers/apply/"
LISTINGS = "/api/dealers/listings/"

MEDIA_OVERRIDE = override_settings(MEDIA_ROOT=tempfile.mkdtemp())


def document(name="logbook.pdf", content=b"%PDF-1.4 pretend"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def photo(name="car.jpg"):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def staff(username, role):
    user = User.objects.create_user(username, f"{username}@goldride.co.ke", "pw")
    Group.objects.get_or_create(name=role)[0].user_set.add(user)
    return user


def application(**overrides):
    """A dealership by default - the kind most of these tests are about.

    Pass seller_type=DealerApplication.INDIVIDUAL for a private seller.
    """
    fields = {
        "seller_type": DealerApplication.DEALERSHIP,
        "dealership_name": "Westlands Motors",
        "contact_name": "Kamau Njoroge",
        "email": "sales@westlandsmotors.co.ke",
        "phone": "0722000000",
        "location": "Nairobi",
        "fleet_size": 24,
        "message": "We have 24 units, mostly Japanese imports.",
    }
    fields.update(overrides)
    return DealerApplication.objects.create(**fields)


def a_dealer(name="Westlands Motors", email="sales@westlands.co.ke", active=True):
    user = User.objects.create_user(name.lower().replace(" ", ""), email, "pw")
    Group.objects.get_or_create(name="Dealer")[0].user_set.add(user)
    return Dealer.objects.create(
        user=user,
        seller_type=DealerApplication.DEALERSHIP,
        name=name,
        contact_name="Kamau",
        phone="0722000000",
        location="Nairobi",
        is_active=active,
    )


def paperwork(seller_type=DealerApplication.DEALERSHIP):
    """A file for every document that kind of applicant must send.

    Built fresh each call: an uploaded file is a stream, and reusing one across
    two requests posts an empty second file.
    """
    kinds = DealerDocument.required_for(seller_type)
    return {
        "documents": [document(f"{kind}.pdf") for kind in kinds],
        "document_kinds": kinds,
    }


def apply_form(paperwork_included=True, **overrides):
    """What the public form posts: the applicant, their first car, and the
    paperwork - flat, because it all arrives as one multipart body and
    multipart has no notion of nesting.

    Pass paperwork_included=False to test what happens without it.
    """
    fields = {
        "seller_type": "dealer",
        "dealership_name": "Westlands Motors",
        "contact_name": "Kamau Njoroge",
        "email": "sales@westlandsmotors.co.ke",
        "phone": "0722000000",
        "location": "Nairobi",
        "car_make": "Toyota",
        "car_model": "Harrier",
        "car_year": "2018",
        "car_price": "3400000",
        "car_mileage_km": "78000",
    }
    if paperwork_included:
        fields.update(paperwork(fields["seller_type"]))
    fields.update(overrides)
    return fields


def a_listing(dealer, **overrides):
    fields = {
        "make": "Toyota",
        "model": "Harrier",
        "year": 2018,
        "price": Decimal("3400000.00"),
        "mileage_km": 78000,
    }
    fields.update(overrides)
    return DealerListing.objects.create(dealer=dealer, **fields)


class ApplyingTests(APITestCase):
    def setUp(self):
        # DRF binds throttle rates at import, so the bucket is cleared rather
        # than the rate overridden - the same as the auth tests.
        cache.clear()

    def test_anybody_may_apply(self):
        response = self.client.post(APPLY, apply_form())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DealerApplication.objects.count(), 1)

    def test_the_applications_cannot_be_read_back(self):
        """A list here is every competitor's prospect list.

        Same rule as inquiries: each public door opens one way.
        """
        application()
        self.assertEqual(self.client.get(APPLY).status_code, 405)

    def test_applying_raises_a_ticket_nobody_has_claimed(self):
        applied = application()

        ticket = Ticket.objects.get(dealer_application=applied)
        self.assertEqual(ticket.kind, Ticket.DEALER)
        self.assertEqual(ticket.status, Ticket.OPEN)
        self.assertIsNone(ticket.claimed_by)

    def test_the_ticket_closes_on_the_decision(self):
        applied = application()
        boss = staff("boss", "Manager")

        approve_application(applied, reviewed_by=boss)

        ticket = Ticket.objects.get(dealer_application=applied)
        self.assertEqual(ticket.status, Ticket.CLOSED)

    def test_the_ticket_names_the_dealership_rather_than_a_car(self):
        applied = application()
        boss = staff("boss", "Manager")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=boss).key}"
        )

        row = self.client.get("/api/staff/tickets/?kind=dealer").data["results"][0]

        self.assertEqual(row["title"], "Westlands Motors")
        self.assertEqual(row["customer"], "Kamau Njoroge")
        self.assertIsNone(row["amount"])


class DecidingTests(APITestCase):
    def setUp(self):
        self.boss = staff("boss", "Manager")
        self.applied = application()
        self.sign_in(self.boss)

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def url(self, action="approve"):
        return f"/api/staff/dealers/applications/{self.applied.pk}/{action}/"

    def test_sales_cannot_take_on_a_dealership(self):
        self.sign_in(staff("asha", "Sales"))

        self.assertEqual(self.client.post(self.url()).status_code, 403)
        self.assertEqual(Dealer.objects.count(), 0)

    def test_approving_creates_the_dealership_and_its_login(self):
        response = self.client.post(self.url(), {"note": "Good reputation."})

        self.assertEqual(response.status_code, 200)
        dealer = Dealer.objects.get()
        self.assertEqual(dealer.name, "Westlands Motors")
        self.assertTrue(dealer.user.groups.filter(name="Dealer").exists())
        self.applied.refresh_from_db()
        self.assertEqual(self.applied.status, DealerApplication.APPROVED)
        self.assertEqual(self.applied.reviewed_by, self.boss)

    def test_the_new_account_has_no_password_anybody_could_know(self):
        # An account is created before its owner has chosen anything, so it
        # must not be signable-into until they do.
        self.client.post(self.url())

        self.assertFalse(Dealer.objects.get().user.has_usable_password())

    def test_approving_twice_creates_one_dealership(self):
        """Two managers on the same application must not make two accounts."""
        first = self.client.post(self.url())
        second = self.client.post(self.url())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(Dealer.objects.count(), 1)
        self.assertEqual(User.objects.filter(groups__name="Dealer").count(), 1)

    def test_an_address_that_is_already_an_account_is_refused(self):
        """Claiming it would hand this dealership somebody else's login.

        The same hole social sign-in was closed against - so a person decides.
        """
        User.objects.create_user("someone", self.applied.email, "pw")

        response = self.client.post(self.url())

        self.assertEqual(response.status_code, 409)
        self.assertIn("already uses that email", response.data["error"])
        self.assertEqual(Dealer.objects.count(), 0)
        self.applied.refresh_from_db()
        self.assertEqual(self.applied.status, DealerApplication.PENDING)

    def test_rejecting_says_so_and_cannot_be_redone(self):
        first = self.client.post(self.url("reject"), {"note": "Too far out."})
        second = self.client.post(self.url("reject"))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.applied.refresh_from_db()
        self.assertEqual(self.applied.status, DealerApplication.REJECTED)
        self.assertEqual(self.applied.decision_note, "Too far out.")

    def test_an_approved_dealership_is_told_how_to_get_in(self):
        mail.outbox = []

        self.client.post(self.url())

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/dealer/activate/", mail.outbox[0].body)


class ActivationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.applied = application()
        self.boss = staff("boss", "Manager")
        self.dealer, _, _ = approve_application(self.applied, reviewed_by=self.boss)
        self.token = make_token(self.dealer.user)

    def url(self, token=None):
        return f"/api/dealers/activate/{token or self.token}/"

    def test_setting_a_password_lets_them_sign_in(self):
        response = self.client.post(
            self.url(), {"password": "a-long-enough-passphrase"}
        )

        self.assertEqual(response.status_code, 200)
        self.dealer.user.refresh_from_db()
        self.assertTrue(
            self.dealer.user.check_password("a-long-enough-passphrase")
        )

    def test_the_link_dies_the_moment_it_is_used(self):
        # The password hash is inside the signature, so setting one
        # invalidates every outstanding copy of the link.
        self.client.post(self.url(), {"password": "a-long-enough-passphrase"})

        again = self.client.post(self.url(), {"password": "something-else-entirely"})

        self.assertEqual(again.status_code, 400)
        self.dealer.user.refresh_from_db()
        self.assertTrue(
            self.dealer.user.check_password("a-long-enough-passphrase")
        )

    def test_a_forged_link_is_refused(self):
        forged = signing.dumps({"uid": self.dealer.user.pk, "pw": "x"}, salt="wrong")

        self.assertEqual(self.client.post(self.url(forged)).status_code, 400)

    def test_a_weak_password_is_refused_with_a_reason(self):
        response = self.client.post(self.url(), {"password": "1234"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_an_expired_link_says_so(self):
        with override_settings(DEALER_ACTIVATION_TIMEOUT=-1):
            with self.assertRaises(ActivationError):
                read_token(self.token)


class PortalTests(APITestCase):
    def setUp(self):
        self.dealer = a_dealer()
        self.other = a_dealer("Mombasa Autos", "sales@mombasaautos.co.ke")
        self.sign_in(self.dealer.user)

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def test_a_dealer_submits_a_car(self):
        response = self.client.post(
            LISTINGS,
            {
                "make": "Toyota",
                "model": "Harrier",
                "year": 2018,
                "price": "3400000.00",
                "mileage_km": 78000,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DealerListing.objects.get().dealer, self.dealer)
        self.assertEqual(response.data["status"], DealerListing.SUBMITTED)

    def test_a_dealer_cannot_file_a_car_under_another_dealership(self):
        # The account decides whose it is, never the request body.
        self.client.post(
            LISTINGS,
            {
                "make": "Toyota",
                "model": "Harrier",
                "year": 2018,
                "price": "3400000.00",
                "dealer": self.other.pk,
            },
        )

        self.assertEqual(DealerListing.objects.get().dealer, self.dealer)

    def test_they_see_only_their_own(self):
        a_listing(self.dealer)
        a_listing(self.other, model="Axio")

        rows = self.client.get(LISTINGS).data["results"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model"], "Harrier")

    def test_somebody_elses_listing_is_a_404_not_a_403(self):
        """The id is in the URL and guessable, so the two must look the same."""
        theirs = a_listing(self.other)

        response = self.client.get(f"{LISTINGS}{theirs.pk}/")

        self.assertEqual(response.status_code, 404)

    def test_a_suspended_dealership_is_shut_out(self):
        self.dealer.is_active = False
        self.dealer.save(update_fields=["is_active"])

        self.assertEqual(self.client.get(LISTINGS).status_code, 403)

    def test_a_customer_account_is_not_a_dealer(self):
        buyer = User.objects.create_user("buyer", "buyer@example.com", "pw")
        Group.objects.get_or_create(name="Customer")[0].user_set.add(buyer)
        self.sign_in(buyer)

        self.assertEqual(self.client.get(LISTINGS).status_code, 403)

    def test_editing_a_rejected_car_puts_it_back_in_the_queue(self):
        listing = a_listing(
            self.dealer,
            status=DealerListing.REJECTED,
            decision_note="Photographs are too dark.",
        )

        response = self.client.patch(
            f"{LISTINGS}{listing.pk}/", {"price": "3200000.00"}
        )

        self.assertEqual(response.status_code, 200)
        listing.refresh_from_db()
        self.assertEqual(listing.status, DealerListing.SUBMITTED)
        self.assertEqual(listing.decision_note, "")

    def test_a_published_car_is_no_longer_theirs_to_edit(self):
        listing = a_listing(self.dealer, status=DealerListing.APPROVED)

        response = self.client.patch(
            f"{LISTINGS}{listing.pk}/", {"price": "1.00"}
        )

        self.assertEqual(response.status_code, 400)
        listing.refresh_from_db()
        self.assertEqual(listing.price, Decimal("3400000.00"))

    def test_withdrawing_keeps_the_record(self):
        listing = a_listing(self.dealer)

        response = self.client.delete(f"{LISTINGS}{listing.pk}/")

        self.assertEqual(response.status_code, 204)
        listing.refresh_from_db()
        self.assertEqual(listing.status, DealerListing.WITHDRAWN)


@MEDIA_OVERRIDE
class PublishingTests(APITestCase):
    def setUp(self):
        self.boss = staff("boss", "Manager")
        self.dealer = a_dealer()
        self.listing = a_listing(self.dealer)
        self.sign_in(self.boss)

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def url(self, action="approve"):
        return f"/api/staff/dealers/listings/{self.listing.pk}/{action}/"

    def test_a_submitted_car_is_not_on_the_public_site(self):
        """The guarantee the whole split between the tables exists for.

        A submission lives in another table entirely, so no missed filter on
        the storefront can leak one.
        """
        self.client.credentials()

        rows = self.client.get("/api/cars/").data["results"]

        self.assertEqual(rows, [])
        self.assertEqual(Car.objects.count(), 0)

    def test_approving_puts_it_on_the_site(self):
        response = self.client.post(self.url(), {"note": "Clean unit."})

        self.assertEqual(response.status_code, 200)
        car = Car.objects.get()
        self.assertEqual(car.make, "Toyota")
        self.assertEqual(car.price, Decimal("3400000.00"))
        self.assertEqual(car.availability, "available")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.published_as, car)

    def test_approving_twice_lists_one_car(self):
        first = self.client.post(self.url())
        second = self.client.post(self.url())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(Car.objects.count(), 1)

    def test_sales_cannot_publish_somebody_elses_car(self):
        self.sign_in(staff("asha", "Sales"))

        self.assertEqual(self.client.post(self.url()).status_code, 403)
        self.assertEqual(Car.objects.count(), 0)

    def test_the_photographs_come_across_and_are_copies(self):
        self.listing.images.create(image=photo("front.jpg"))
        self.listing.images.create(image=photo("rear.jpg"))

        self.client.post(self.url())

        car = Car.objects.get()
        self.assertTrue(car.image)
        self.assertEqual(car.images.count(), 1)
        # Copied, not shared: deleting the submission must not blank the car.
        self.assertNotEqual(car.image.name, self.listing.images.first().image.name)

    def test_a_blank_description_never_names_the_dealership(self):
        """The buyer sees an ordinary Goldride listing.

        A generated description is the one place that decision could leak onto
        a public page without anybody choosing it.
        """
        self.client.post(self.url())

        car = Car.objects.get()
        self.assertIn("Toyota Harrier", car.description)
        self.assertNotIn("Westlands", car.description)

    def test_the_public_listing_carries_nothing_identifying_the_dealer(self):
        self.client.post(self.url())
        self.client.credentials()

        car = self.client.get("/api/cars/").data["results"][0]
        body = str(car).lower()

        self.assertNotIn("westlands", body)
        self.assertNotIn("dealer", body)

    def test_rejecting_lists_nothing_and_tells_them_why(self):
        mail.outbox = []

        response = self.client.post(self.url("reject"), {"note": "Photos too dark."})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Car.objects.count(), 0)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, DealerListing.REJECTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Photos too dark.", mail.outbox[0].body)

    def test_a_rejected_car_cannot_be_approved_without_being_resubmitted(self):
        self.client.post(self.url("reject"))

        response = self.client.post(self.url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Car.objects.count(), 0)

    def test_publish_refuses_to_run_twice_even_called_directly(self):
        approve_listing(self.listing, reviewed_by=self.boss)
        self.listing.refresh_from_db()

        car, message = self.listing.publish()

        self.assertIsNone(car)
        self.assertEqual(Car.objects.count(), 1)
