"""Private sellers and dealerships, which are not the same applicant.

A person with one car and a business with a fleet are asked for different
things, and the difference has to survive all the way through: the queue, the
staff screens, the invitation email and the roster. The tests here are the ones
that would catch it drifting apart - a private seller showing up as a blank
dealership, or a dealership being asked for a passport number.
"""

from django.core import mail
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from tickets.models import Ticket

from .models import Dealer, DealerApplication, DealerDocument
from .services import approve_application
from .tests import apply_form, document, paperwork, staff

APPLY = "/api/dealers/apply/"


def individual_form(**overrides):
    """What a private seller posts: themselves, their ID, and their car.

    Their paperwork is a shorter list than a dealership's - they are not being
    licensed, so it is only who they are and whether the car is theirs.
    """
    fields = apply_form(paperwork_included=False)
    fields.pop("dealership_name")
    fields.update(
        {
            "seller_type": "individual",
            "contact_name": "Aisha Mwangi",
            "email": "aisha@example.com",
            "id_number": "24681012",
        }
    )
    fields.update(paperwork(DealerApplication.INDIVIDUAL))
    fields.update(overrides)
    return fields


class ApplyingAsAnIndividualTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_a_person_may_list_their_own_car(self):
        response = self.client.post(APPLY, individual_form())

        self.assertEqual(response.status_code, 201)
        applied = DealerApplication.objects.get()
        self.assertEqual(applied.seller_type, DealerApplication.INDIVIDUAL)
        self.assertEqual(applied.id_number, "24681012")
        self.assertEqual(applied.dealership_name, "")

    def test_a_person_is_known_by_their_own_name(self):
        """`display_name` is the one answer to "what do we call them".

        Without it a private seller shows up as a blank dealership on the
        queue, in the invitation and on the roster.
        """
        self.client.post(APPLY, individual_form())

        self.assertEqual(DealerApplication.objects.get().display_name, "Aisha Mwangi")

    def test_a_person_is_asked_for_an_id(self):
        response = self.client.post(APPLY, individual_form(id_number=""))

        self.assertEqual(response.status_code, 400)
        self.assertIn("id_number", response.data)
        self.assertEqual(DealerApplication.objects.count(), 0)

    def test_a_person_is_never_asked_for_a_trading_name(self):
        # Typed in before the seller type was switched, say. Cleared rather
        # than refused - losing the whole form over it would be unkind.
        response = self.client.post(
            APPLY, individual_form(dealership_name="Aisha Motors", fleet_size="9")
        )

        self.assertEqual(response.status_code, 201)
        applied = DealerApplication.objects.get()
        self.assertEqual(applied.dealership_name, "")
        self.assertIsNone(applied.fleet_size)

    def test_their_ticket_carries_their_name(self):
        self.client.post(APPLY, individual_form())
        boss = staff("boss", "Manager")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=boss).key}"
        )

        row = self.client.get("/api/staff/tickets/?kind=dealer").data["results"][0]

        self.assertEqual(row["title"], "Aisha Mwangi")
        self.assertEqual(row["customer"], "Aisha Mwangi")

    def test_the_office_is_told_which_kind_of_seller_it_is(self):
        mail.outbox = []

        self.client.post(APPLY, individual_form())

        body = mail.outbox[0].body
        self.assertIn("private seller", body)
        self.assertIn("24681012", body)

    def test_approving_a_person_names_the_account_after_them(self):
        self.client.post(APPLY, individual_form())
        applied = DealerApplication.objects.get()

        dealer, ok, _ = approve_application(applied, reviewed_by=staff("b", "Manager"))

        self.assertTrue(ok)
        self.assertEqual(dealer.name, "Aisha Mwangi")
        self.assertEqual(dealer.seller_type, DealerApplication.INDIVIDUAL)
        self.assertEqual(Ticket.objects.get().status, Ticket.CLOSED)


class ApplyingAsADealershipTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_a_dealership_is_known_by_its_trading_name(self):
        self.client.post(APPLY, apply_form())

        applied = DealerApplication.objects.get()
        self.assertEqual(applied.seller_type, DealerApplication.DEALERSHIP)
        self.assertEqual(applied.display_name, "Westlands Motors")
        self.assertTrue(applied.is_dealership)

    def test_a_dealership_is_asked_for_its_name(self):
        response = self.client.post(APPLY, apply_form(dealership_name=""))

        self.assertEqual(response.status_code, 400)
        self.assertIn("dealership_name", response.data)

    def test_a_dealership_is_not_asked_for_a_passport(self):
        # It proves itself with paperwork, not with a director's ID.
        response = self.client.post(APPLY, apply_form())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DealerApplication.objects.get().id_number, "")

    def test_the_office_is_told_the_fleet_rather_than_an_id(self):
        mail.outbox = []

        self.client.post(APPLY, apply_form(fleet_size="24"))

        body = mail.outbox[0].body
        self.assertIn("dealership", body)
        self.assertIn("Fleet: 24", body)

    def test_approving_a_dealership_names_the_account_after_the_business(self):
        self.client.post(APPLY, apply_form())
        applied = DealerApplication.objects.get()

        dealer, ok, _ = approve_application(applied, reviewed_by=staff("b", "Manager"))

        self.assertTrue(ok)
        self.assertEqual(dealer.name, "Westlands Motors")
        self.assertEqual(dealer.seller_type, DealerApplication.DEALERSHIP)


class NobodyIsAskedForAWebsiteTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_the_field_is_gone_from_both_models(self):
        """It was asked for and never used. Removed rather than left blank.

        A column nobody fills is a column somebody eventually renders on a
        staff screen as an empty row.
        """
        self.assertNotIn(
            "website", [field.name for field in DealerApplication._meta.get_fields()]
        )
        self.assertNotIn(
            "website", [field.name for field in Dealer._meta.get_fields()]
        )

    def test_sending_one_anyway_changes_nothing(self):
        response = self.client.post(APPLY, apply_form(website="https://example.com"))

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("website", response.data)


class RequiredPaperworkTests(APITestCase):
    """What Kenya requires of a motor vehicle dealer, asked for up front.

    Checked at the door rather than left to staff to chase: a dealership with
    no trade licence is not a decision anybody can make, and finding that out
    by email a day later wastes both sides' time.
    """

    def setUp(self):
        cache.clear()

    def test_a_dealership_must_send_the_licensing_documents(self):
        response = self.client.post(APPLY, apply_form(paperwork_included=False))

        self.assertEqual(response.status_code, 400)
        message = response.data["documents"][0]
        for expected in [
            "Certificate of incorporation",
            "KRA PIN",
            "Trade licence",
            "National ID",
            "Dealer's application form",
            "Headed application letter",
            "Insurance",
        ]:
            self.assertIn(expected, message)

    def test_everything_missing_is_named_at_once(self):
        """Seven refusals to learn seven things is not a form, it is a maze."""
        form = apply_form(paperwork_included=False)
        form.update(
            {
                "documents": [document("kra.pdf"), document("id.pdf")],
                "document_kinds": ["kra_pin", "id"],
            }
        )

        response = self.client.post(APPLY, form, format="multipart")

        message = response.data["documents"][0]
        self.assertNotIn("KRA PIN", message)
        self.assertNotIn("National ID", message)
        self.assertIn("Trade licence", message)
        self.assertIn("Insurance", message)

    def test_vat_is_not_demanded_of_everybody(self):
        """Registration only bites above the turnover threshold.

        Requiring it would refuse every dealer below that threshold, which is
        most of the ones worth having.
        """
        response = self.client.post(APPLY, apply_form())

        self.assertEqual(response.status_code, 201)
        self.assertNotIn(
            DealerDocument.VAT_CERTIFICATE,
            DealerDocument.REQUIRED_OF_DEALERSHIP,
        )

    def test_a_private_seller_is_asked_for_far_less(self):
        # They are not being licensed. Only: are you who you say, and is the
        # car yours to sell.
        self.assertEqual(
            DealerDocument.REQUIRED_OF_INDIVIDUAL,
            [DealerDocument.ID_DOCUMENT, DealerDocument.LOGBOOK],
        )

    def test_a_private_seller_must_still_prove_the_car_is_theirs(self):
        form = individual_form()
        form.update(
            {
                "documents": [document("id.pdf")],
                "document_kinds": ["id"],
            }
        )

        response = self.client.post(APPLY, form, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Logbook", response.data["documents"][0])

    def test_nothing_is_written_when_paperwork_is_missing(self):
        self.client.post(APPLY, apply_form(paperwork_included=False))

        self.assertEqual(DealerApplication.objects.count(), 0)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_a_dealership_may_send_more_than_the_minimum(self):
        form = apply_form()
        form["documents"] = form["documents"] + [document("vat.pdf")]
        form["document_kinds"] = form["document_kinds"] + ["vat"]

        response = self.client.post(APPLY, form, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DealerDocument.objects.count(), 8)
