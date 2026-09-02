"""The live half: what reaches the other side, and who may connect at all."""

from decimal import Decimal

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TransactionTestCase, override_settings
from rest_framework.authtoken.models import Token

from goldride_project.asgi import application

from .consumers import NOT_ALLOWED, NOT_AUTHENTICATED

User = get_user_model()

# The in-memory layer is per process, which is exactly what a test wants: no
# Redis to stand up, and no state surviving between cases.
MEMORY_LAYER = override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)


@database_sync_to_async
def make(username, group):
    user = User.objects.create_user(username, f"{username}@example.com", "pw")
    Group.objects.get_or_create(name=group)[0].user_set.add(user)
    return user, Token.objects.create(user=user).key


@database_sync_to_async
def ticket_for(customer):
    """A real enquiry, so the ticket arrives through the signal."""
    from cars.models import Car
    from inquiries.models import Inquiry

    car = Car.objects.create(
        make="Toyota", model="Prado", year=2019,
        price=Decimal("4250000.00"), description="A car.",
    )
    inquiry = Inquiry.objects.create(
        car=car, customer=customer, name=customer.username,
        phone="0712345678", email=customer.email, message="Still available?",
    )
    return inquiry.ticket.pk


@database_sync_to_async
def reply_over_rest(ticket_id, agent, body):
    from .access import conversation_for
    from .services import send_message

    send_message(
        conversation_for(agent, ticket_id, create=True), agent, body, from_staff=True
    )


def socket(path, token=None):
    """Connects the way the browser will.

    The token goes in as a subprotocol rather than the query string, so it
    stays out of proxy logs. The Origin header is here because the routing is
    wrapped in AllowedHostsOriginValidator - a websocket is exempt from the
    same-origin policy, so without that wrapper any page on the internet could
    open one carrying the visitor's credentials. A client that sends no origin
    is refused exactly like a stranger, which is correct and would otherwise
    look like a broken consumer.
    """
    communicator = WebsocketCommunicator(application, path)
    communicator.scope["headers"].append((b"origin", b"http://localhost"))
    if token:
        communicator.scope["headers"].append(
            (b"sec-websocket-protocol", f"token, {token}".encode())
        )
    return communicator


@MEMORY_LAYER
class SocketConnectionTests(TransactionTestCase):
    async def test_a_customer_can_open_their_own_ticket(self):
        customer, token = await make("wanjiru", "Customer")
        ticket = await ticket_for(customer)

        client = socket(f"/ws/chat/{ticket}/", token)
        connected, subprotocol = await client.connect()

        self.assertTrue(connected)
        self.assertEqual(subprotocol, "token")
        await client.disconnect()

    async def test_no_token_is_refused(self):
        customer, _ = await make("wanjiru", "Customer")
        ticket = await ticket_for(customer)

        connected, code = await socket(f"/ws/chat/{ticket}/").connect()

        self.assertFalse(connected)
        self.assertEqual(code, NOT_AUTHENTICATED)

    async def test_a_junk_token_is_refused(self):
        customer, _ = await make("wanjiru", "Customer")
        ticket = await ticket_for(customer)

        connected, code = await socket(
            f"/ws/chat/{ticket}/", "not-a-real-token"
        ).connect()

        self.assertFalse(connected)
        self.assertEqual(code, NOT_AUTHENTICATED)

    async def test_a_customer_cannot_open_another_persons_ticket(self):
        """The rule that matters most here: the ticket id is in the URL, so
        it is guessable, and the socket has to check ownership exactly like
        the REST endpoint does."""
        owner, _ = await make("wanjiru", "Customer")
        ticket = await ticket_for(owner)
        _, nosy_token = await make("nosy", "Customer")

        connected, code = await socket(f"/ws/chat/{ticket}/", nosy_token).connect()

        self.assertFalse(connected)
        self.assertEqual(code, NOT_ALLOWED)

    async def test_a_customer_cannot_open_the_staff_socket(self):
        customer, token = await make("wanjiru", "Customer")
        ticket = await ticket_for(customer)

        connected, code = await socket(
            f"/ws/staff/chat/{ticket}/", token
        ).connect()

        self.assertFalse(connected)
        self.assertEqual(code, NOT_ALLOWED)

    async def test_staff_cannot_open_a_ticket_that_does_not_exist(self):
        _, token = await make("asha", "Sales")

        connected, code = await socket("/ws/staff/chat/999999/", token).connect()

        self.assertFalse(connected)
        self.assertEqual(code, NOT_ALLOWED)


@MEMORY_LAYER
class SocketDeliveryTests(TransactionTestCase):
    async def both_ends(self):
        customer, customer_token = await make("wanjiru", "Customer")
        agent, staff_token = await make("asha", "Sales")
        ticket = await ticket_for(customer)

        theirs = socket(f"/ws/chat/{ticket}/", customer_token)
        ours = socket(f"/ws/staff/chat/{ticket}/", staff_token)
        await theirs.connect()
        await ours.connect()
        return ticket, agent, theirs, ours

    async def test_what_a_customer_says_reaches_staff_live(self):
        _, _, theirs, ours = await self.both_ends()

        await theirs.send_json_to({"body": "Is the Prado still there?"})
        received = await ours.receive_json_from()

        self.assertEqual(received["message"]["body"], "Is the Prado still there?")
        self.assertFalse(received["message"]["from_staff"])
        self.assertEqual(received["message"]["sender_name"], "wanjiru")

        await theirs.disconnect()
        await ours.disconnect()

    async def test_a_reply_reaches_the_customer_as_goldride(self):
        """Shaped per audience on the way out: staff see the colleague, the
        customer sees the dealership."""
        _, _, theirs, ours = await self.both_ends()

        await ours.send_json_to({"body": "It is, yes."})
        at_the_customer = await theirs.receive_json_from()
        at_the_staff = await ours.receive_json_from()

        self.assertEqual(at_the_customer["message"]["sender_name"], "Goldride")
        self.assertEqual(at_the_staff["message"]["sender_name"], "asha")

        await theirs.disconnect()
        await ours.disconnect()

    async def test_an_empty_message_is_refused_without_closing_the_socket(self):
        _, _, theirs, ours = await self.both_ends()

        await theirs.send_json_to({"body": "   "})
        response = await theirs.receive_json_from()

        self.assertIn("error", response)
        await theirs.disconnect()
        await ours.disconnect()

    async def test_a_message_sent_over_rest_still_arrives_on_the_socket(self):
        """One write path. Somebody replying from a screen with no socket
        open must still reach a customer who has one."""
        ticket, agent, theirs, ours = await self.both_ends()

        await reply_over_rest(ticket, agent, "Over REST")
        received = await theirs.receive_json_from()

        self.assertEqual(received["message"]["body"], "Over REST")

        await theirs.disconnect()
        await ours.disconnect()
