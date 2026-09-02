"""One conversation per ticket, and only for the person whose ticket it is."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from cars.models import Car
from imports.models import ImportRequest
from inquiries.models import Inquiry
from purchases.models import PurchaseRequest

from .models import Conversation
from .services import send_message

User = get_user_model()
MINE = "/api/chat/"
INBOX = "/api/staff/chats/"


def person(username, group):
    user = User.objects.create_user(username, f"{username}@example.com", "pw")
    Group.objects.get_or_create(name=group)[0].user_set.add(user)
    return user


def a_car(model="Prado"):
    return Car.objects.create(
        make="Toyota", model=model, year=2019,
        price=Decimal("4250000.00"), description="A car.",
    )


def enquiry_ticket(customer, message=""):
    """An enquiry raises its ticket through the signal, like the real thing.

    No message by default: an enquiry that carries one also seeds the
    conversation with it (see EnquiryBecomesAConversationTests), and most of
    these cases want a ticket to hang a thread on rather than a thread that
    has already started.
    """
    return Inquiry.objects.create(
        car=a_car(), customer=customer, name=customer.username,
        phone="0712345678", email=customer.email, message=message,
    ).ticket


def thread_on(ticket):
    """The conversation for a ticket, whether or not an enquiry seeded it."""
    return Conversation.objects.get_or_create(ticket=ticket)[0]


def approval_ticket(customer):
    return PurchaseRequest.objects.create(
        customer=customer, car=a_car("Hilux"),
        preferred_method="card", phone="0712345678",
    ).ticket


def guest_sourcing_ticket():
    """No account behind it - a guest may raise an import request."""
    return ImportRequest.objects.create(
        contact_name="Passing trade", email="guest@example.com",
        phone="0712345678", make="Toyota", model="Land Cruiser", year=2019,
    ).ticket


class ChatOnTicketsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.customer = person("wanjiru", "Customer")
        self.agent = person("asha", "Sales")
        self.ticket = enquiry_ticket(self.customer)

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )

    def url(self, ticket=None):
        return f"{MINE}{(ticket or self.ticket).pk}/"

    # --- the customer's side ----------------------------------------------

    def test_opening_a_ticket_starts_its_conversation(self):
        self.sign_in(self.customer)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["ticket_id"], self.ticket.pk)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_each_ticket_gets_its_own(self):
        """The whole point of the change: what was said about the purchase
        does not turn up under an unrelated enquiry."""
        second = approval_ticket(self.customer)
        self.sign_in(self.customer)

        self.client.post(self.url(), {"body": "About the enquiry"})
        self.client.post(self.url(second), {"body": "About the purchase"})

        self.assertEqual(Conversation.objects.count(), 2)
        first = self.client.get(self.url()).data["messages"]
        self.assertEqual([m["body"] for m in first], ["About the enquiry"])

    def test_another_persons_ticket_is_not_found(self):
        """404, not 403 - either answer would confirm the ticket is real."""
        stranger = person("stranger", "Customer")
        theirs = enquiry_ticket(stranger)
        self.sign_in(self.customer)

        self.assertEqual(self.client.get(self.url(theirs)).status_code, 404)
        self.assertEqual(
            self.client.post(self.url(theirs), {"body": "Hello"}).status_code, 404
        )

    def test_a_ticket_that_does_not_exist_answers_the_same_way(self):
        self.sign_in(self.customer)

        self.assertEqual(self.client.get(f"{MINE}999999/").status_code, 404)

    def test_the_account_lists_their_threads(self):
        second = approval_ticket(self.customer)
        self.sign_in(self.customer)
        self.client.post(self.url(), {"body": "One"})
        self.client.post(self.url(second), {"body": "Two"})

        rows = self.client.get(MINE).data

        self.assertEqual(
            sorted(row["ticket_id"] for row in rows),
            sorted([self.ticket.pk, second.pk]),
        )

    def test_the_list_leaves_out_other_peoples(self):
        stranger = person("stranger", "Customer")
        other = enquiry_ticket(stranger)
        send_message(thread_on(other), stranger, "Private", False)
        self.sign_in(self.customer)

        self.assertEqual(self.client.get(MINE).data, [])

    # --- the staff side ----------------------------------------------------

    def test_the_inbox_says_which_ticket_it_is_about(self):
        conversation = thread_on(self.ticket)
        send_message(conversation, self.customer, "Anyone there?", False)
        self.sign_in(self.agent)

        row = self.client.get(INBOX).data["results"][0]

        self.assertEqual(row["customer_name"], "wanjiru")
        self.assertEqual(row["ticket_id"], self.ticket.pk)
        self.assertEqual(row["ticket_kind"], "enquiry")
        self.assertEqual(row["unread"], 1)

    def test_staff_can_reply_on_any_ticket(self):
        self.sign_in(self.agent)

        response = self.client.post(
            f"{INBOX}{self.ticket.pk}/", {"body": "Yes, it is."}
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["from_staff"])

    def test_there_is_nobody_to_reply_to_on_a_guest_ticket(self):
        """A guest has contact details but no account, so there is nowhere to
        deliver a chat message - it has to go by email or phone."""
        guest = guest_sourcing_ticket()
        self.sign_in(self.agent)

        response = self.client.post(f"{INBOX}{guest.pk}/", {"body": "Hello?"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("no customer account", str(response.data["detail"]))

    def test_a_customer_cannot_reach_the_inbox(self):
        self.sign_in(self.customer)

        self.assertEqual(self.client.get(INBOX).status_code, 403)

    # --- the conversation outlives the ticket ------------------------------

    def test_a_closed_ticket_can_still_be_written_to(self):
        """Closing a ticket ends the work, not the talking."""
        conversation = thread_on(self.ticket)
        send_message(conversation, self.customer, "Thanks", False)
        self.ticket.close()
        self.sign_in(self.customer)

        response = self.client.post(self.url(), {"body": "One more thing"})

        self.assertEqual(response.status_code, 201)

    def test_a_reply_to_settled_work_still_shows_in_the_inbox(self):
        """The part that makes "stays open" safe: it must not be invisible
        behind a closed status."""
        conversation = thread_on(self.ticket)
        self.ticket.close()
        send_message(conversation, self.customer, "Still here?", False)
        self.sign_in(self.agent)

        rows = self.client.get(f"{INBOX}?unread=true").data["results"]

        self.assertEqual([row["ticket_id"] for row in rows], [self.ticket.pk])
        self.assertEqual(rows[0]["ticket_status"], "closed")

    # --- unread ------------------------------------------------------------

    def test_replying_marks_the_other_sides_words_as_seen(self):
        conversation = thread_on(self.ticket)
        send_message(conversation, self.customer, "Hello?", False)
        self.assertEqual(conversation.unread_for_staff(), 1)

        send_message(conversation, self.agent, "Hello.", True)

        self.assertEqual(conversation.unread_for_staff(), 0)

    def test_the_customer_has_something_unread_until_they_open_it(self):
        conversation = thread_on(self.ticket)
        send_message(conversation, self.agent, "Your car has shipped.", True)
        self.sign_in(self.customer)

        self.assertEqual(self.client.get(self.url()).data["unread"], 1)
        self.client.post(f"{MINE}{self.ticket.pk}/read/")

        self.assertEqual(self.client.get(self.url()).data["unread"], 0)

    def test_staff_names_are_not_shown_to_the_customer(self):
        conversation = thread_on(self.ticket)
        send_message(conversation, self.agent, "Yes, it is.", True)
        self.sign_in(self.customer)

        response = self.client.get(self.url())

        self.assertEqual(response.data["messages"][0]["sender_name"], "Goldride")

    def test_staff_see_which_colleague_replied(self):
        conversation = thread_on(self.ticket)
        send_message(conversation, self.agent, "Mine", True)
        self.sign_in(self.agent)

        response = self.client.get(f"{INBOX}{self.ticket.pk}/")

        self.assertEqual(response.data["messages"][0]["sender_name"], "asha")


class EnquiryBecomesAConversationTests(APITestCase):
    """An enquiry and its answer are the first two things said."""

    def setUp(self):
        cache.clear()
        self.customer = person("wanjiru", "Customer")
        self.agent = person("asha", "Sales")

    def an_enquiry(self, message="Is this still available?"):
        return Inquiry.objects.create(
            car=a_car(), customer=self.customer, name="Wanjiru",
            phone="0712345678", email=self.customer.email, message=message,
        )

    def test_the_question_starts_the_thread(self):
        enquiry = self.an_enquiry()

        conversation = Conversation.objects.get(ticket=enquiry.ticket)
        message = conversation.messages.first()

        self.assertEqual(message.body, "Is this still available?")
        self.assertFalse(message.from_staff)
        self.assertEqual(message.sender, self.customer)

    def test_it_is_waiting_on_us_from_the_moment_it_arrives(self):
        enquiry = self.an_enquiry()

        conversation = Conversation.objects.get(ticket=enquiry.ticket)

        self.assertEqual(conversation.unread_for_staff(), 1)

    def test_the_answer_joins_the_same_thread(self):
        from inquiries.services import record_reply

        enquiry = self.an_enquiry()
        record_reply(enquiry, self.agent, "Yes, it is. Come and see it.")

        bodies = [
            (m.from_staff, m.body)
            for m in Conversation.objects.get(ticket=enquiry.ticket).messages.all()
        ]

        self.assertEqual(
            bodies,
            [
                (False, "Is this still available?"),
                (True, "Yes, it is. Come and see it."),
            ],
        )

    def test_answering_still_closes_the_ticket(self):
        """The conversation carrying on does not mean the work is unfinished."""
        from inquiries.services import record_reply

        enquiry = self.an_enquiry()
        record_reply(enquiry, self.agent, "Yes, it is.")

        enquiry.ticket.refresh_from_db()
        self.assertEqual(enquiry.ticket.status, "closed")

    def test_answering_still_emails_them(self):
        """Both places on purpose - they get it without signing in."""
        from django.core import mail
        from inquiries.services import record_reply

        enquiry = self.an_enquiry()
        mail.outbox = []

        record_reply(enquiry, self.agent, "Yes, it is.")

        self.assertEqual(len(mail.outbox), 1)

    def test_the_customer_can_carry_on_from_there(self):
        from inquiries.services import record_reply

        enquiry = self.an_enquiry()
        record_reply(enquiry, self.agent, "Yes, it is.")
        self.sign_in(self.customer)

        response = self.client.post(
            f"{MINE}{enquiry.ticket.pk}/", {"body": "Saturday morning?"}
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Conversation.objects.get(ticket=enquiry.ticket).messages.count(), 3
        )

    def test_an_empty_enquiry_starts_nothing(self):
        """The message is optional on the form - a phone number and a car is
        a valid enquiry, and an empty bubble is not a conversation."""
        enquiry = self.an_enquiry(message="")

        self.assertFalse(
            Conversation.objects.filter(ticket=enquiry.ticket).exists()
        )

    def sign_in(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )
