from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from goldride_app.permissions import IsCustomer, IsSales

from .access import conversation_for
from .models import Conversation
from .serializers import (
    ConversationSerializer,
    InboxConversationSerializer,
    MessageSerializer,
)
from .services import send_message

# The joins every listing needs: the ticket, and the customer hanging off
# whichever subject it points at.
CONVERSATIONS = Conversation.objects.select_related(
    "ticket",
    "ticket__purchase_request__customer",
    "ticket__import_request__customer",
    "ticket__inquiry__customer",
)


class TicketConversationMixin:
    """Resolve the conversation, or 404 - never 403.

    A customer poking at ticket ids must not be able to tell "not yours" from
    "does not exist"; either answer would confirm the ticket is real.
    """

    for_staff = False

    def resolve(self, request, ticket_id, create=False):
        return conversation_for(request.user, ticket_id, create=create)

    def read(self, conversation):
        return Response(
            ConversationSerializer(
                conversation, context={"for_staff": self.for_staff}
            ).data
        )

    def write(self, request, conversation):
        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = send_message(
            conversation,
            sender=request.user,
            body=serializer.validated_data["body"],
            from_staff=self.for_staff,
        )
        return Response(
            MessageSerializer(
                message, context={"for_staff": self.for_staff}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class MyThreadsView(generics.ListAPIView):
    """Every conversation this customer has, one per ticket.

    Their way in: with chat attached to work, there is no single thread to
    open, so the account lists what they have going.
    """

    serializer_class = InboxConversationSerializer
    permission_classes = [IsCustomer]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        # Three columns because a ticket points at its subject with a real
        # foreign key per kind, and the customer hangs off whichever one is
        # set. The alternative - filtering in Python on Ticket.customer -
        # reads better and loads every conversation in the table to do it.
        theirs = (
            Q(ticket__purchase_request__customer=user)
            | Q(ticket__import_request__customer=user)
            | Q(ticket__inquiry__customer=user)
        )
        return CONVERSATIONS.filter(theirs)


class MyConversationView(TicketConversationMixin, APIView):
    permission_classes = [IsCustomer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"
    for_staff = False

    @extend_schema(responses={200: ConversationSerializer})
    def get(self, request, ticket_id):
        conversation = self.resolve(request, ticket_id, create=True)
        if conversation is None:
            return Response({"detail": "Not found."}, status=404)
        return self.read(conversation)

    @extend_schema(request=MessageSerializer, responses={201: MessageSerializer})
    def post(self, request, ticket_id):
        conversation = self.resolve(request, ticket_id, create=True)
        if conversation is None:
            return Response({"detail": "Not found."}, status=404)
        return self.write(request, conversation)


class MyConversationReadView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(request=None, responses={204: None})
    def post(self, request, ticket_id):
        conversation = conversation_for(request.user, ticket_id)
        if conversation is None:
            return Response({"detail": "Not found."}, status=404)
        conversation.mark_read(by_staff=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffInboxView(generics.ListAPIView):
    """Every conversation, most recently spoken in first.

    Not filtered by ticket status. A conversation outlives its ticket, so a
    reply to settled work still lands here rather than behind a closed badge
    nobody opens.
    """

    serializer_class = InboxConversationSerializer
    permission_classes = [IsSales]

    def get_queryset(self):
        queryset = CONVERSATIONS.exclude(last_message_at=None)

        if self.request.query_params.get("unread") in ("true", "1"):
            ids = [c.pk for c in queryset if c.unread_for_staff()]
            queryset = queryset.filter(pk__in=ids)
        return queryset


class StaffConversationView(TicketConversationMixin, APIView):
    permission_classes = [IsSales]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"
    for_staff = True

    @extend_schema(responses={200: ConversationSerializer})
    def get(self, request, ticket_id):
        conversation = self.resolve(request, ticket_id, create=True)
        if conversation is None:
            return Response({"detail": "Not found."}, status=404)
        return self.read(conversation)

    @extend_schema(request=MessageSerializer, responses={201: MessageSerializer})
    def post(self, request, ticket_id):
        conversation = self.resolve(request, ticket_id, create=True)
        if conversation is None:
            return Response(
                {"detail": "This ticket has no customer account to reply to."},
                status=400,
            )
        return self.write(request, conversation)


class StaffConversationReadView(APIView):
    permission_classes = [IsSales]

    @extend_schema(request=None, responses={204: None})
    def post(self, request, ticket_id):
        conversation = conversation_for(request.user, ticket_id)
        if conversation is None:
            return Response({"detail": "Not found."}, status=404)
        conversation.mark_read(by_staff=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
