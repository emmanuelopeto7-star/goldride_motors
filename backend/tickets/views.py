from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from goldride_app.permissions import IsSales
from inquiries.services import record_reply

from .models import Ticket
from .serializers import TicketSerializer


class TicketListView(generics.ListAPIView):
    serializer_class = TicketSerializer
    permission_classes = [IsSales]

    def get_queryset(self):
        queryset = Ticket.objects.with_subjects()

        # Settled work is out of the way unless it is asked for by name. The
        # queue is meant to be what is left to do; a list that grows forever
        # is one nobody reads.
        requested_status = self.request.query_params.get("status")
        queryset = (
            queryset.filter(status=requested_status)
            if requested_status
            else queryset.live()
        )

        kind = self.request.query_params.get("kind")
        if kind:
            queryset = queryset.filter(kind=kind)

        if self.request.query_params.get("mine") in ("true", "1"):
            queryset = queryset.owned_by(self.request.user)

        # Oldest first. The model orders newest-first, which is right for a
        # history and wrong for a queue: it puts this morning's arrivals on
        # top and sinks the request that has been waiting three weeks onto
        # page three. In a queue, age is the risk.
        if requested_status == Ticket.CLOSED:
            # Settled work reads the other way - it is a record, and the
            # useful end is the one just finished.
            return queryset.order_by("-closed_at", "-created_at")
        return queryset.order_by("created_at")


class TicketDetailView(generics.RetrieveAPIView):
    queryset = Ticket.objects.with_subjects()
    serializer_class = TicketSerializer
    permission_classes = [IsSales]


class TicketClaimView(APIView):
    """Take a ticket. The one endpoint where losing is a normal outcome."""

    permission_classes = [IsSales]

    @extend_schema(
        request=None,
        responses={200: TicketSerializer, 409: TicketSerializer},
        description="Claim an open ticket. Returns 409 with the ticket as it "
                    "now stands if another agent got there first - the caller "
                    "shows who owns it rather than a bare failure.",
    )
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)

        if ticket.claim(request.user):
            return Response(TicketSerializer(ticket).data)

        # Re-read before answering: the useful thing to tell the agent is who
        # has it now, and that is only known after the race is lost.
        ticket.refresh_from_db()
        return Response(TicketSerializer(ticket).data, status=status.HTTP_409_CONFLICT)


class TicketReleaseView(APIView):
    permission_classes = [IsSales]

    @extend_schema(
        request=None,
        responses={200: TicketSerializer, 403: None},
        description="Put a claimed ticket back in the queue. The owner may "
                    "always do this; anyone else must be a Manager.",
    )
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)

        # Taking work off a colleague is a supervisor's act, not a peer's -
        # otherwise two agents can pass one ticket back and forth all morning.
        if ticket.claimed_by != request.user and not _is_manager(request.user):
            return Response(
                {"detail": "Only the agent holding this ticket, or a manager, "
                           "can release it."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not ticket.release():
            return Response(
                {"detail": "This ticket is not claimed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(TicketSerializer(ticket).data)


class TicketCloseView(APIView):
    permission_classes = [IsSales]

    @extend_schema(
        request=None,
        responses={200: TicketSerializer, 403: None},
        description="Mark a ticket done. Closing normally happens by itself "
                    "when the request is decided; this is for the ones that "
                    "end some other way - a customer who stops replying.",
    )
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)

        if ticket.claimed_by != request.user and not _is_manager(request.user):
            return Response(
                {"detail": "Only the agent holding this ticket, or a manager, "
                           "can close it."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not ticket.close():
            return Response(
                {"detail": "This ticket is already closed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(TicketSerializer(ticket).data)


class TicketReplyView(APIView):
    """Answer an enquiry, once.

    The endpoint that carries the whole point of the queue: with several
    agents on the same list, the customer must get one reply, not one from
    each of them. Sending is refused - not merely discouraged - the moment
    somebody else has answered.
    """

    permission_classes = [IsSales]

    @extend_schema(
        request=inline_serializer(
            "EnquiryReply", {"message": serializers.CharField()}
        ),
        responses={200: TicketSerializer, 409: TicketSerializer},
        description="Reply to the enquiry behind this ticket. Emails the "
                    "customer, records who answered and closes the ticket. "
                    "Returns 409 if another agent has already answered - "
                    "nothing is sent in that case.",
    )
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)

        if ticket.kind != Ticket.ENQUIRY:
            return Response(
                {"detail": "Only an enquiry can be replied to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"message": ["Write something to send."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        claimed, emailed, detail = record_reply(ticket.inquiry, request.user, message)

        if not claimed:
            ticket.refresh_from_db()
            body = TicketSerializer(ticket).data
            body["detail"] = detail
            return Response(body, status=status.HTTP_409_CONFLICT)

        ticket.refresh_from_db()
        body = TicketSerializer(ticket).data
        body["emailed"] = emailed
        body["detail"] = detail
        return Response(body)


def _is_manager(user):
    return user.is_superuser or user.groups.filter(name="Manager").exists()
