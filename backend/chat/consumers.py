"""The live half of the conversation.

Both consumers join the same group - one per conversation - so a message
written by either side reaches the other without a refresh. What differs is
who may join, and how each side is allowed to see the other.

Nothing is written here that the REST endpoints do not also write: a socket
message goes through chat.services.send_message like everything else, so the
rules live in one place and a client that cannot hold a socket open is not a
second-class citizen.
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .access import conversation_for, is_staff
from .models import Conversation
from .services import send_message

# Close codes. 4000+ is the range reserved for the application, and saying
# which of the two went wrong saves an afternoon: "not signed in" and "not
# yours" look identical from the browser otherwise.
NOT_AUTHENTICATED = 4401
NOT_ALLOWED = 4403


class BaseChatConsumer(AsyncJsonWebsocketConsumer):
    from_staff = False

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=NOT_AUTHENTICATED)
            return

        self.conversation_id = await self.resolve(user)
        if self.conversation_id is None:
            await self.close(code=NOT_ALLOWED)
            return

        self.group = group_for(self.conversation_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept(
            subprotocol="token" if self.scope.get("token_subprotocol") else None
        )

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        body = (content or {}).get("body", "")
        body = body.strip() if isinstance(body, str) else ""
        if not body:
            await self.send_json({"error": "Write something to send."})
            return

        await self.write(body)

    @database_sync_to_async
    def write(self, body):
        conversation = Conversation.objects.get(pk=self.conversation_id)
        send_message(
            conversation,
            sender=self.scope["user"],
            body=body,
            from_staff=self.from_staff,
        )

    async def chat_message(self, event):
        """Fan-out from the channel layer. Shaped per audience here rather
        than at the point of broadcast, so the one payload can serve both."""
        message = dict(event["message"])
        if not self.for_staff and message["from_staff"]:
            # A customer is talking to Goldride, not to whoever is on shift.
            message["sender_name"] = "Goldride"
        await self.send_json({"message": message})


class CustomerChatConsumer(BaseChatConsumer):
    from_staff = False
    for_staff = False

    @database_sync_to_async
    def resolve(self, user):
        """Same rule as the REST endpoint, from the same function.

        A socket that decided for itself who owns a ticket would be a second
        copy of the rule, and the copy nobody remembers to update.
        """
        if not user.groups.filter(name="Customer").exists():
            return None

        ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        conversation = conversation_for(user, ticket_id, create=True)
        return conversation.pk if conversation else None


class StaffChatConsumer(BaseChatConsumer):
    from_staff = True
    for_staff = True

    @database_sync_to_async
    def resolve(self, user):
        if not is_staff(user):
            return None

        ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        conversation = conversation_for(user, ticket_id, create=True)
        return conversation.pk if conversation else None


def group_for(conversation_id):
    return f"chat_{conversation_id}"
