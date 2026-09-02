from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from .models import Conversation, Message

# Return types are annotated on every SerializerMethodField below. Without
# them drf-spectacular cannot tell what a method returns and documents it as a
# plain string, so /api/docs/ shows an unread *count* as text - which is worse
# than no schema, because it is confidently wrong.


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "body", "from_staff", "sender_name", "created_at"]
        read_only_fields = ["from_staff", "sender_name", "created_at"]

    def get_sender_name(self, message) -> str:
        """Who said it, as the reader should see it.

        A customer does not need to know which agent replied - "Goldride" is
        the voice they are talking to, and naming whoever happened to be on
        shift invites them to ask for that person by name next time. Staff do
        need to know, because it is how they see who has already answered.
        """
        if message.sender is None:
            return "Goldride" if message.from_staff else "Someone"

        if message.from_staff and not self.context.get("for_staff"):
            return "Goldride"

        return message.sender.get_full_name() or message.sender.username

    def validate_body(self, body):
        body = body.strip()
        if not body:
            raise serializers.ValidationError("Write something to send.")
        return body


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    unread = serializers.SerializerMethodField()
    ticket_id = serializers.IntegerField(source="ticket.pk", read_only=True)
    ticket_kind_label = serializers.CharField(
        source="ticket.get_kind_display", read_only=True
    )
    ticket_status = serializers.CharField(source="ticket.status", read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id", "ticket_id", "ticket_kind_label", "ticket_status",
            "created_at", "last_message_at", "unread", "messages",
        ]

    def get_unread(self, conversation) -> int:
        return (
            conversation.unread_for_staff()
            if self.context.get("for_staff")
            else conversation.unread_for_customer()
        )


class InboxConversationSerializer(serializers.ModelSerializer):
    """A row in the staff inbox: who, about what, what they last said.

    The ticket is named because the conversation is about the work - "Wanjiru"
    is not enough to know whether this is her sourcing request or the enquiry
    she sent last month. `ticket_status` rides along because a conversation
    outlives its ticket, and answering a settled matter reads differently.
    """

    customer_name = serializers.SerializerMethodField()
    ticket_id = serializers.IntegerField(source="ticket.pk", read_only=True)
    ticket_kind = serializers.CharField(source="ticket.kind", read_only=True)
    ticket_kind_label = serializers.CharField(
        source="ticket.get_kind_display", read_only=True
    )
    ticket_status = serializers.CharField(source="ticket.status", read_only=True)
    last_message = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id", "customer_name",
            "ticket_id", "ticket_kind", "ticket_kind_label", "ticket_status",
            "last_message", "last_message_at", "unread",
        ]

    def get_customer_name(self, conversation) -> str:
        customer = conversation.customer
        if customer is None:
            return "Unknown"
        return customer.get_full_name() or customer.username

    @extend_schema_field(inline_serializer('LastMessage', {
        'body': serializers.CharField(),
        'from_staff': serializers.BooleanField(),
        'created_at': serializers.DateTimeField(),
    }))
    def get_last_message(self, conversation):
        last = conversation.messages.last()
        if last is None:
            return None
        return {
            "body": last.body[:120],
            "from_staff": last.from_staff,
            "created_at": last.created_at,
        }

    def get_unread(self, conversation) -> int:
        return conversation.unread_for_staff()
