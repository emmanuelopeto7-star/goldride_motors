"""Applying with a car, its photographs and its paperwork.

Three promises are worth guarding here, and each would be expensive to break:

Photographs end up on the storefront and paperwork never does - a logbook names
a registered owner and an ID is an ID, so the API describes a document but
never hands out a path to it.

Approving an application is one decision that both takes the dealership on and
puts their car on the site, and it either all happens or none of it does.

And a car arriving this way is held to exactly the same rules as one submitted
through the portal later, because it lands on the same model.
"""

import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from cars.models import Car
from tickets.models import Ticket

from .models import (
    MAX_DOCUMENT_BYTES,
    Dealer,
    DealerApplication,
    DealerDocument,
    DealerListing,
)
from .tests import a_dealer, application, apply_form, document, photo, staff

User = get_user_model()

APPLY = "/api/dealers/apply/"

MEDIA_OVERRIDE = override_settings(MEDIA_ROOT=tempfile.mkdtemp())


class ApplyingWithACarTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_an_application_brings_the_car_it_is_about(self):
        """Staff decide with a car in front of them, not a promise of one.

        A dealership and its first car are one errand, and the car lands on the
        same DealerListing every other submission uses - one path into
        inventory, not two.
        """
        response = self.client.post(APPLY, apply_form())

        self.assertEqual(response.status_code, 201)
        listing = DealerListing.objects.get()
        self.assertEqual(listing.make, "Toyota")
        self.assertEqual(listing.price, Decimal("3400000.00"))
        self.assertEqual(listing.application, DealerApplication.objects.get())
        # No dealership exists yet - that is what they are applying for.
        self.assertIsNone(listing.dealer)
        self.assertEqual(listing.status, DealerListing.SUBMITTED)

    def test_an_application_without_a_car_is_refused(self):
        form = {
            key: value
            for key, value in apply_form().items()
            if not key.startswith("car_")
        }

        response = self.client.post(APPLY, form)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DealerApplication.objects.count(), 0)

    def test_a_car_priced_at_nothing_is_refused(self):
        # The same rule the portal enforces: a car arriving this way cannot be
        # held to looser standards than one submitted later.
        response = self.client.post(APPLY, apply_form(car_price="0"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DealerApplication.objects.count(), 0)

    def test_nothing_is_written_when_the_car_is_refused(self):
        """One transaction: an application with no car is unreviewable."""
        self.client.post(APPLY, apply_form(car_year="1066"))

        self.assertEqual(DealerApplication.objects.count(), 0)
        self.assertEqual(DealerListing.objects.count(), 0)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_the_ticket_still_names_the_dealership(self):
        self.client.post(APPLY, apply_form())

        ticket = Ticket.objects.get()
        self.assertEqual(ticket.kind, Ticket.DEALER)
        self.assertEqual(ticket.status, Ticket.OPEN)


@MEDIA_OVERRIDE
class AttachmentsTests(APITestCase):
    """Photographs and paperwork, which are not the same thing at all."""

    def setUp(self):
        cache.clear()

    def test_photographs_land_on_the_car(self):
        form = apply_form()
        form["photos"] = [photo("front.jpg"), photo("rear.jpg")]

        response = self.client.post(APPLY, form, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DealerListing.objects.get().images.count(), 2)

    def test_paperwork_lands_on_the_application_with_its_label(self):
        """Each file keeps the label it was sent with.

        The pairing is positional - multipart has no other way to associate a
        label with a file - so a slip here silently files a logbook as an
        insurance certificate.
        """
        form = apply_form()
        form["documents"] = form["documents"] + [document("extra-logbook.pdf")]
        form["document_kinds"] = form["document_kinds"] + ["logbook"]

        self.client.post(APPLY, form, format="multipart")

        pairs = {
            row.filename: row.kind for row in DealerDocument.objects.all()
        }
        self.assertEqual(pairs["extra-logbook.pdf"], DealerDocument.LOGBOOK)
        self.assertEqual(pairs["trade_licence.pdf"], DealerDocument.TRADE_LICENCE)
        self.assertEqual(pairs["insurance.pdf"], DealerDocument.INSURANCE)

    def test_an_unlabelled_document_is_other_rather_than_refused(self):
        # One more file than labels: the tail falls back rather than failing.
        form = apply_form()
        form["documents"] = form["documents"] + [document("something.pdf")]

        self.client.post(APPLY, form, format="multipart")

        extra = DealerDocument.objects.get(file__endswith="something.pdf")
        self.assertEqual(extra.kind, DealerDocument.OTHER)

    def test_a_made_up_label_never_reaches_the_column(self):
        form = apply_form()
        form["documents"] = form["documents"] + [document("x.pdf")]
        form["document_kinds"] = form["document_kinds"] + ["../../etc/passwd"]

        self.client.post(APPLY, form, format="multipart")

        forged = DealerDocument.objects.get(file__endswith="x.pdf")
        self.assertEqual(forged.kind, DealerDocument.OTHER)

    def test_an_executable_is_not_a_document(self):
        form = apply_form()
        form["documents"] = [document("payload.exe", b"MZ")]

        response = self.client.post(APPLY, form, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DealerApplication.objects.count(), 0)

    def test_a_file_over_the_ceiling_is_refused(self):
        # An unauthenticated upload path without a ceiling is somewhere to park
        # arbitrary files.
        oversized = document("huge.pdf", b"x" * (MAX_DOCUMENT_BYTES + 1))
        form = apply_form()
        form["documents"] = [oversized]

        response = self.client.post(APPLY, form, format="multipart")

        self.assertEqual(response.status_code, 400)

    def test_the_photograph_count_is_capped(self):
        form = apply_form()
        form["photos"] = [photo(f"{index}.jpg") for index in range(13)]

        response = self.client.post(APPLY, form, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DealerListing.objects.count(), 0)


@MEDIA_OVERRIDE
class DocumentPrivacyTests(APITestCase):
    """Paperwork is personal data and never leaves with the JSON."""

    def setUp(self):
        cache.clear()
        self.applied = application()
        self.document = DealerDocument.objects.create(
            application=self.applied,
            kind=DealerDocument.LOGBOOK,
            file=document("logbook.pdf"),
        )
        self.url = f"/api/staff/dealers/documents/{self.document.pk}/"

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def test_a_stranger_cannot_download_paperwork(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_a_customer_cannot_download_paperwork(self):
        buyer = User.objects.create_user("buyer", "buyer@example.com", "pw")
        Group.objects.get_or_create(name="Customer")[0].user_set.add(buyer)
        self.sign_in(buyer)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_a_dealer_cannot_download_paperwork(self):
        other = a_dealer("Mombasa Autos", "sales@mombasaautos.co.ke")
        self.sign_in(other.user)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_staff_get_the_file_as_a_download(self):
        # Attachment, not inline: a logbook opening in a browser tab is a
        # logbook in somebody's history and cache.
        self.sign_in(staff("asha", "Sales"))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_the_api_never_hands_out_a_path_to_the_file(self):
        """The row is described; the bytes come from the checked endpoint.

        A URL in the JSON is a URL in a browser history, a proxy log, and
        anywhere else the payload gets pasted.
        """
        self.sign_in(staff("boss", "Manager"))

        row = self.client.get(
            f"/api/staff/dealers/applications/{self.applied.pk}/"
        ).data

        self.assertEqual(row["documents"][0]["kind"], DealerDocument.LOGBOOK)
        self.assertEqual(row["documents"][0]["filename"], "logbook.pdf")
        self.assertNotIn("file", row["documents"][0])
        self.assertNotIn("dealer-documents", str(row))


@MEDIA_OVERRIDE
class ApprovalListsTheCarTests(APITestCase):
    """Approving the application is what puts the car on the site."""

    def setUp(self):
        cache.clear()
        self.boss = staff("boss", "Manager")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.boss).key}"
        )
        form = apply_form()
        form["photos"] = [photo("front.jpg"), photo("rear.jpg")]
        self.client.post(APPLY, form, format="multipart")
        self.applied = DealerApplication.objects.get()

    def url(self, action="approve"):
        return f"/api/staff/dealers/applications/{self.applied.pk}/{action}/"

    def test_the_car_is_not_on_the_site_before_the_decision(self):
        self.assertEqual(Car.objects.count(), 0)

    def test_approving_takes_them_on_and_lists_the_car_at_once(self):
        response = self.client.post(self.url(), {"note": "Good reputation."})

        self.assertEqual(response.status_code, 200)
        car = Car.objects.get()
        self.assertEqual(car.make, "Toyota")
        self.assertEqual(car.availability, "available")
        self.assertTrue(car.image)
        self.assertEqual(car.images.count(), 1)

        listing = DealerListing.objects.get()
        self.assertEqual(listing.status, DealerListing.APPROVED)
        self.assertEqual(listing.published_as, car)
        self.assertEqual(listing.reviewed_by, self.boss)
        # It belongs to the dealership that was just created, and still
        # remembers the application it arrived on.
        self.assertEqual(listing.dealer, Dealer.objects.get())
        self.assertEqual(listing.application, self.applied)

    def test_approving_twice_lists_one_car(self):
        first = self.client.post(self.url())
        second = self.client.post(self.url())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(Car.objects.count(), 1)
        self.assertEqual(Dealer.objects.count(), 1)

    def test_sales_cannot_list_a_car_by_approving_a_dealership(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=staff('asha', 'Sales')).key}"
        )

        self.assertEqual(self.client.post(self.url()).status_code, 403)
        self.assertEqual(Car.objects.count(), 0)

    def test_rejecting_lists_nothing(self):
        self.client.post(self.url("reject"), {"note": "Not for us."})

        self.assertEqual(Car.objects.count(), 0)
        self.assertEqual(Dealer.objects.count(), 0)
        self.assertEqual(
            DealerListing.objects.get().status, DealerListing.SUBMITTED
        )

    def test_the_invitation_says_the_car_is_already_live(self):
        # They hear it from us rather than stumbling across their own car.
        mail.outbox = []

        self.client.post(self.url())

        body = mail.outbox[-1].body
        self.assertIn("Already live on the site", body)
        self.assertIn("Toyota Harrier", body)

    def test_a_refused_approval_leaves_nothing_behind(self):
        """The whole approval is one transaction.

        A dealership with an account but no car, or a car with no dealership,
        are both worse than a refusal nobody has acted on yet.
        """
        User.objects.create_user("someone", self.applied.email, "pw")

        response = self.client.post(self.url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Car.objects.count(), 0)
        self.assertEqual(Dealer.objects.count(), 0)
        self.assertEqual(
            DealerListing.objects.get().status, DealerListing.SUBMITTED
        )

    def test_the_published_car_still_names_nobody(self):
        self.client.post(self.url())
        self.client.credentials()

        car = self.client.get("/api/cars/").data["results"][0]

        self.assertNotIn("westlands", str(car).lower())
