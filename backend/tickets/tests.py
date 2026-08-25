from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from django.core import mail

from cars.models import Car
from imports.models import ImportRequest
from inquiries.models import Inquiry
from inquiries.services import record_reply
from purchases.models import PurchaseRequest

from .models import Ticket

User = get_user_model()


def make_agent(username):
    return User.objects.create_user(username, f"{username}@goldride.co.ke", "pw")


def make_purchase_request():
    # A fresh buyer each time: several of these tests raise more than one
    # request, and they are not the same customer.
    buyer = make_agent(f"buyer{User.objects.count()}")
    car = Car.objects.create(
        make="Toyota",
        model="Prado",
        year=2019,
        price=Decimal("4250000.00"),
        description="A car.",
    )
    return PurchaseRequest.objects.create(
        customer=buyer,
        car=car,
        preferred_method="card",
        phone="0712345678",
    )


def make_import_request():
    return ImportRequest.objects.create(
        contact_name="Wanjiru",
        email="wanjiru@example.com",
        phone="0712345678",
        make="Toyota",
        model="Land Cruiser",
        year=2019,
    )


class TicketIsRaisedTests(TestCase):
    """Tickets replace the queues, so nothing may arrive without one."""

    def test_a_purchase_request_raises_an_approval_ticket(self):
        request = make_purchase_request()

        self.assertEqual(request.ticket.kind, Ticket.APPROVAL)
        self.assertEqual(request.ticket.status, Ticket.OPEN)

    def test_an_import_request_raises_a_sourcing_ticket(self):
        request = make_import_request()

        self.assertEqual(request.ticket.kind, Ticket.SOURCING)
        self.assertEqual(request.ticket.status, Ticket.OPEN)

    def test_a_decision_closes_the_ticket(self):
        request = make_purchase_request()

        request.status = "approved"
        request.save()

        request.ticket.refresh_from_db()
        self.assertEqual(request.ticket.status, Ticket.CLOSED)
        self.assertIsNotNone(request.ticket.closed_at)

    def test_an_ordinary_edit_leaves_the_ticket_alone(self):
        """Only a decision settles it - editing the note must not."""
        request = make_purchase_request()

        request.message = "Calling back on Tuesday."
        request.save()

        request.ticket.refresh_from_db()
        self.assertEqual(request.ticket.status, Ticket.OPEN)

    def test_saving_a_request_twice_does_not_raise_a_second_ticket(self):
        request = make_purchase_request()
        request.save()

        self.assertEqual(Ticket.objects.filter(purchase_request=request).count(), 1)


class ClaimTests(TestCase):
    def setUp(self):
        self.ticket = make_purchase_request().ticket
        self.asha = make_agent("asha")
        self.brian = make_agent("brian")

    def test_claiming_takes_ownership(self):
        took = self.ticket.claim(self.asha)

        self.assertTrue(took)
        self.assertEqual(self.ticket.claimed_by, self.asha)
        self.assertEqual(self.ticket.status, Ticket.CLAIMED)
        self.assertIsNotNone(self.ticket.claimed_at)

    def test_two_agents_clicking_at_once_do_not_both_get_it(self):
        """The reason claim() is an UPDATE and not an if.

        Both agents load the ticket screen. Both copies say claimed_by is
        None, because both were read before either clicked - which is exactly
        what a check-then-save would trust. Only one click may win.
        """
        asha_copy = Ticket.objects.get(pk=self.ticket.pk)
        brian_copy = Ticket.objects.get(pk=self.ticket.pk)
        self.assertIsNone(asha_copy.claimed_by)
        self.assertIsNone(brian_copy.claimed_by)

        asha_won = asha_copy.claim(self.asha)
        brian_won = brian_copy.claim(self.brian)

        self.assertTrue(asha_won)
        self.assertFalse(brian_won)

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.claimed_by, self.asha)

    def test_the_loser_is_told_who_has_it(self):
        """A refused claim still refreshes nothing - the caller re-reads to
        show the agent who owns it now, rather than a bare failure."""
        self.ticket.claim(self.asha)
        stale = Ticket.objects.get(pk=self.ticket.pk)

        self.assertFalse(stale.claim(self.brian))
        stale.refresh_from_db()
        self.assertEqual(stale.claimed_by, self.asha)

    def test_releasing_puts_it_back_in_the_queue(self):
        self.ticket.claim(self.asha)

        self.assertTrue(self.ticket.release())
        self.assertEqual(self.ticket.status, Ticket.OPEN)
        self.assertIsNone(self.ticket.claimed_by)
        self.assertIsNone(self.ticket.claimed_at)

    def test_releasing_an_unclaimed_ticket_changes_nothing(self):
        self.assertFalse(self.ticket.release())

    def test_a_closed_ticket_cannot_be_claimed(self):
        self.ticket.close()

        self.assertFalse(self.ticket.claim(self.asha))

    def test_closing_keeps_the_record_of_who_dealt_with_it(self):
        self.ticket.claim(self.asha)
        self.ticket.close()

        self.assertEqual(self.ticket.status, Ticket.CLOSED)
        self.assertEqual(self.ticket.claimed_by, self.asha)

    def test_closing_twice_reports_the_second_as_nothing_done(self):
        self.ticket.close()

        self.assertFalse(self.ticket.close())


class ConstraintTests(TestCase):
    """The rules that must hold even if a future caller forgets them."""

    def test_the_kind_must_match_the_subject(self):
        request = make_import_request()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Ticket.objects.create(kind=Ticket.APPROVAL, import_request=request)

    def test_a_ticket_must_point_at_something(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ticket.objects.create(kind=Ticket.APPROVAL)

    def test_an_open_ticket_cannot_have_an_owner(self):
        ticket = make_purchase_request().ticket
        agent = make_agent("carol")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Ticket.objects.filter(pk=ticket.pk).update(claimed_by=agent)


class QueueTests(TestCase):
    def test_the_live_queue_leaves_out_settled_work(self):
        open_ticket = make_purchase_request().ticket
        settled = make_import_request()
        settled.status = "cancelled"
        settled.save()

        live = Ticket.objects.live()

        self.assertEqual([t.pk for t in live], [open_ticket.pk])

    def test_a_page_of_tickets_is_one_query(self):
        for _ in range(3):
            make_purchase_request()
            make_import_request()

        with self.assertNumQueries(1):
            for ticket in Ticket.objects.with_subjects():
                # Whatever the list renders: the customer's name and the car.
                str(ticket.subject)


class TicketApiTests(APITestCase):
    url = "/api/staff/tickets/"

    def setUp(self):
        self.asha = make_agent("asha")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(self.asha)
        self.brian = make_agent("brian")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(self.brian)
        self.manager = make_agent("mo")
        Group.objects.get_or_create(name="Manager")[0].user_set.add(self.manager)
        self.ticket = make_purchase_request().ticket

    def sign_in(self, user):
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_a_customer_cannot_see_the_queue(self):
        self.sign_in(make_agent("nosy"))

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_the_queue_shows_the_work_and_who_it_is_for(self):
        self.sign_in(self.asha)

        row = self.client.get(self.url).data["results"][0]

        self.assertEqual(row["kind"], "approval")
        self.assertEqual(row["title"], "2019 Toyota Prado")
        self.assertEqual(row["status"], "open")
        self.assertIsNone(row["claimed_by_username"])

    def test_settled_work_is_out_of_the_queue(self):
        request = make_purchase_request()
        request.status = "rejected"
        request.save()
        self.sign_in(self.asha)

        ids = [row["id"] for row in self.client.get(self.url).data["results"]]

        self.assertEqual(ids, [self.ticket.pk])

    def test_the_queue_can_be_narrowed_to_one_kind(self):
        make_import_request()
        self.sign_in(self.asha)

        rows = self.client.get(f"{self.url}?kind=sourcing").data["results"]

        self.assertEqual([row["kind"] for row in rows], ["sourcing"])

    def test_an_agent_can_ask_for_only_their_own(self):
        mine = make_import_request().ticket
        mine.claim(self.asha)
        self.sign_in(self.asha)

        rows = self.client.get(f"{self.url}?mine=true").data["results"]

        self.assertEqual([row["id"] for row in rows], [mine.pk])

    def test_claiming_returns_the_ticket_with_the_owner_on_it(self):
        self.sign_in(self.asha)

        response = self.client.post(f"{self.url}{self.ticket.pk}/claim/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["claimed_by_username"], "asha")
        self.assertEqual(response.data["status"], "claimed")

    def test_losing_the_race_is_a_conflict_naming_the_winner(self):
        """The agent who lost needs to know who has it, not just that they
        failed - otherwise they ask the room."""
        self.ticket.claim(self.asha)
        self.sign_in(self.brian)

        response = self.client.post(f"{self.url}{self.ticket.pk}/claim/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["claimed_by_username"], "asha")

    def test_a_peer_cannot_take_work_off_someone(self):
        self.ticket.claim(self.asha)
        self.sign_in(self.brian)

        response = self.client.post(f"{self.url}{self.ticket.pk}/release/")

        self.assertEqual(response.status_code, 403)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.claimed_by, self.asha)

    def test_a_manager_can_take_work_off_someone(self):
        self.ticket.claim(self.asha)
        self.sign_in(self.manager)

        response = self.client.post(f"{self.url}{self.ticket.pk}/release/")

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.OPEN)

    def test_the_owner_can_give_it_back(self):
        self.ticket.claim(self.asha)
        self.sign_in(self.asha)

        response = self.client.post(f"{self.url}{self.ticket.pk}/release/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["claimed_by_username"])

    def test_the_owner_can_close_it(self):
        self.ticket.claim(self.asha)
        self.sign_in(self.asha)

        response = self.client.post(f"{self.url}{self.ticket.pk}/close/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "closed")

    def test_closing_an_already_closed_ticket_is_refused(self):
        self.ticket.claim(self.asha)
        self.ticket.close()
        self.sign_in(self.asha)

        response = self.client.post(f"{self.url}{self.ticket.pk}/close/")

        self.assertEqual(response.status_code, 400)


def make_inquiry(email="wanjiru@example.com"):
    car = Car.objects.create(
        make="Toyota", model="Harrier", year=2018,
        price=Decimal("3100000.00"), description="A car.",
    )
    return Inquiry.objects.create(
        car=car, name="Wanjiru", phone="0722000111", email=email,
        message="Is this still available?",
    )


class EnquiryTicketTests(TestCase):
    """The kind the queue was really built for.

    An enquiry has no status column and no decision to make - it is answered,
    or it is not. With several agents on one list the risk is not that nobody
    replies, it is that three people do.
    """

    def setUp(self):
        self.inquiry = make_inquiry()
        self.asha = make_agent("asha")
        self.brian = make_agent("brian")

    def test_an_enquiry_raises_a_ticket(self):
        self.assertEqual(self.inquiry.ticket.kind, Ticket.ENQUIRY)
        self.assertEqual(self.inquiry.ticket.status, Ticket.OPEN)

    def test_replying_records_who_answered_and_what_they_said(self):
        record_reply(self.inquiry, self.asha, "Yes, it is still with us.")

        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.reply, "Yes, it is still with us.")
        self.assertEqual(self.inquiry.replied_by, self.asha)
        self.assertIsNotNone(self.inquiry.replied_at)

    def test_replying_closes_the_ticket(self):
        """Out of the queue the moment it is answered, so nobody picks it up
        and answers it again."""
        record_reply(self.inquiry, self.asha, "Yes, still available.")

        self.inquiry.ticket.refresh_from_db()
        self.assertEqual(self.inquiry.ticket.status, Ticket.CLOSED)

    def test_replying_emails_the_customer(self):
        mail.outbox = []

        claimed, emailed, _ = record_reply(self.inquiry, self.asha, "Still here.")

        self.assertTrue(claimed)
        self.assertTrue(emailed)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["wanjiru@example.com"])

    def test_two_agents_replying_at_once_send_one_email(self):
        """The failure this whole feature exists to stop.

        Both agents opened the enquiry before either hit send, so both hold a
        copy with no reply on it. The customer must not receive two different
        answers to one question.
        """
        asha_copy = Inquiry.objects.get(pk=self.inquiry.pk)
        brian_copy = Inquiry.objects.get(pk=self.inquiry.pk)
        self.assertIsNone(asha_copy.replied_at)
        self.assertIsNone(brian_copy.replied_at)
        mail.outbox = []

        asha_won, _, _ = record_reply(asha_copy, self.asha, "Yes, still available.")
        brian_won, brian_sent, detail = record_reply(
            brian_copy, self.brian, "Sorry, that one sold."
        )

        self.assertTrue(asha_won)
        self.assertFalse(brian_won)
        self.assertFalse(brian_sent)
        self.assertIn("already been answered", detail)
        self.assertEqual(len(mail.outbox), 1)

    def test_the_first_answer_is_the_one_kept(self):
        record_reply(self.inquiry, self.asha, "Yes, still available.")
        record_reply(self.inquiry, self.brian, "Sorry, that one sold.")

        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.reply, "Yes, still available.")
        self.assertEqual(self.inquiry.replied_by, self.asha)

    def test_an_enquiry_with_no_email_is_recorded_as_a_call(self):
        inquiry = make_inquiry(email="")
        mail.outbox = []

        claimed, emailed, detail = record_reply(inquiry, self.asha, "Rang her.")

        self.assertTrue(claimed)
        self.assertFalse(emailed)
        self.assertIn("recorded as a call", detail)
        self.assertEqual(len(mail.outbox), 0)
        inquiry.ticket.refresh_from_db()
        self.assertEqual(inquiry.ticket.status, Ticket.CLOSED)


class EnquiryReplyApiTests(APITestCase):
    url_for = "/api/staff/tickets/{}/reply/"

    def setUp(self):
        self.inquiry = make_inquiry()
        self.asha = make_agent("asha")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(self.asha)
        self.brian = make_agent("brian")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(self.brian)

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def test_an_agent_can_answer_and_the_ticket_closes(self):
        self.sign_in(self.asha)

        response = self.client.post(
            self.url_for.format(self.inquiry.ticket.pk),
            {"message": "Yes, still available."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "closed")
        self.assertTrue(response.data["emailed"])

    def test_a_second_agent_is_refused_and_nothing_is_sent(self):
        self.sign_in(self.asha)
        self.client.post(
            self.url_for.format(self.inquiry.ticket.pk),
            {"message": "Yes, still available."},
        )
        mail.outbox = []
        self.sign_in(self.brian)

        response = self.client.post(
            self.url_for.format(self.inquiry.ticket.pk),
            {"message": "Sorry, that one sold."},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already been answered", response.data["detail"])
        self.assertEqual(len(mail.outbox), 0)

    def test_an_empty_message_is_refused(self):
        self.sign_in(self.asha)

        response = self.client.post(
            self.url_for.format(self.inquiry.ticket.pk), {"message": "   "}
        )

        self.assertEqual(response.status_code, 400)

    def test_only_an_enquiry_can_be_replied_to(self):
        ticket = make_purchase_request().ticket
        self.sign_in(self.asha)

        response = self.client.post(
            self.url_for.format(ticket.pk), {"message": "Hello."}
        )

        self.assertEqual(response.status_code, 400)


class QueueOrderTests(APITestCase):
    """Age is the risk. The thing waiting longest belongs at the top."""

    url = "/api/staff/tickets/"

    def setUp(self):
        self.agent = make_agent("orderly")
        Group.objects.get_or_create(name="Sales")[0].user_set.add(self.agent)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.agent).key}"
        )

    def age(self, ticket, days):
        stamp = timezone.now() - timedelta(days=days)
        Ticket.objects.filter(pk=ticket.pk).update(created_at=stamp)
        return ticket

    def test_the_oldest_waiting_ticket_comes_first(self):
        recent = make_purchase_request().ticket
        old = self.age(make_import_request().ticket, days=21)
        middling = self.age(make_purchase_request().ticket, days=5)

        rows = self.client.get(self.url).data["results"]

        self.assertEqual(
            [row["id"] for row in rows], [old.pk, middling.pk, recent.pk]
        )

    def test_closed_work_reads_as_history_instead(self):
        """A record, not a queue: the one just finished is the useful end."""
        first = make_purchase_request().ticket
        first.close()
        second = make_import_request().ticket
        second.close()

        rows = self.client.get(f"{self.url}?status=closed").data["results"]

        self.assertEqual([row["id"] for row in rows][:2], [second.pk, first.pk])
