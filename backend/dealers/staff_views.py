"""The office side: reviewing dealerships and the cars they submit.

Who decides what follows the rule already running through the staff API -
Sales reads and works, a Manager decides. Taking on a dealership and putting
somebody else's car on the site are both commitments, so both are a Manager's.
"""

from django.http import FileResponse, Http404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics
from rest_framework.response import Response
from rest_framework.views import APIView

from goldride_app.permissions import IsManager, IsSales

from .models import Dealer, DealerApplication, DealerDocument, DealerListing
from .serializers import (
    DealerSerializer,
    DecisionSerializer,
    StaffDealerApplicationSerializer,
    StaffDealerListingSerializer,
)
from .services import (
    approve_application,
    approve_listing,
    reject_application,
    reject_listing,
)


class StaffDealerApplicationListView(generics.ListAPIView):
    serializer_class = StaffDealerApplicationSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status"]
    search_fields = ["dealership_name", "contact_name", "email", "location"]

    def get_queryset(self):
        return DealerApplication.objects.select_related("reviewed_by", "dealer")


class StaffDealerApplicationDetailView(generics.RetrieveAPIView):
    serializer_class = StaffDealerApplicationSerializer
    permission_classes = [IsSales]
    queryset = DealerApplication.objects.select_related("reviewed_by", "dealer")


class _Decision(APIView):
    """Shared plumbing: read the note, find the row, hand it to a service."""

    permission_classes = [IsManager]
    model = None

    def get_object(self, pk):
        return self.model.objects.filter(pk=pk).first()

    def note(self, request):
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data.get("note", "")


@extend_schema(
    request=DecisionSerializer,
    responses={200: StaffDealerApplicationSerializer},
    description="Take on a dealership: creates their account and posts the "
                "invitation to set a password.",
)
class StaffApproveApplicationView(_Decision):
    model = DealerApplication

    def post(self, request, pk):
        application = self.get_object(pk)
        if application is None:
            return Response({"error": "no such application"}, status=404)

        dealer, ok, message = approve_application(
            application, reviewed_by=request.user, note=self.note(request)
        )
        if not ok:
            # 409: somebody else got there first, or a person has to untangle
            # an email address that is already an account.
            return Response({"error": message}, status=409)

        application.refresh_from_db()
        return Response(
            {
                "application": StaffDealerApplicationSerializer(application).data,
                "dealer": DealerSerializer(dealer).data,
            }
        )


@extend_schema(request=DecisionSerializer, responses={200: StaffDealerApplicationSerializer})
class StaffRejectApplicationView(_Decision):
    model = DealerApplication

    def post(self, request, pk):
        application = self.get_object(pk)
        if application is None:
            return Response({"error": "no such application"}, status=404)

        ok, message = reject_application(
            application, reviewed_by=request.user, note=self.note(request)
        )
        if not ok:
            return Response({"error": message}, status=409)

        application.refresh_from_db()
        return Response(StaffDealerApplicationSerializer(application).data)


class StaffDealerListView(generics.ListAPIView):
    serializer_class = DealerSerializer
    permission_classes = [IsSales]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "contact_name", "location"]
    queryset = Dealer.objects.select_related("user")


class StaffDealerDetailView(generics.RetrieveUpdateAPIView):
    """Correct a dealership's details, or suspend it.

    Deliberately no DELETE, for the reason the team screen has none: their
    listings and the orders behind them outlive the relationship.
    """

    serializer_class = DealerSerializer
    permission_classes = [IsManager]
    queryset = Dealer.objects.select_related("user")


class StaffDealerListingListView(generics.ListAPIView):
    serializer_class = StaffDealerListingSerializer
    permission_classes = [IsSales]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status", "dealer"]
    search_fields = ["make", "model", "dealer__name"]

    def get_queryset(self):
        return DealerListing.objects.select_related(
            "dealer", "reviewed_by", "published_as"
        ).prefetch_related("images")


class StaffDealerListingDetailView(generics.RetrieveAPIView):
    serializer_class = StaffDealerListingSerializer
    permission_classes = [IsSales]

    def get_queryset(self):
        return DealerListing.objects.select_related(
            "dealer", "reviewed_by", "published_as"
        ).prefetch_related("images")


@extend_schema(
    request=DecisionSerializer,
    responses={200: StaffDealerListingSerializer},
    description="Publish a dealer's car. Creates the public listing and its "
                "gallery from the submitted photographs.",
)
class StaffApproveListingView(_Decision):
    model = DealerListing

    def post(self, request, pk):
        listing = self.get_object(pk)
        if listing is None:
            return Response({"error": "no such submission"}, status=404)

        car, ok, message = approve_listing(
            listing, reviewed_by=request.user, note=self.note(request)
        )
        if not ok:
            return Response({"error": message}, status=409)

        listing.refresh_from_db()
        return Response(
            {
                "listing": StaffDealerListingSerializer(listing).data,
                "car_id": car.id,
            }
        )


@extend_schema(request=DecisionSerializer, responses={200: StaffDealerListingSerializer})
class StaffRejectListingView(_Decision):
    model = DealerListing

    def post(self, request, pk):
        listing = self.get_object(pk)
        if listing is None:
            return Response({"error": "no such submission"}, status=404)

        ok, message = reject_listing(
            listing, reviewed_by=request.user, note=self.note(request)
        )
        if not ok:
            return Response({"error": message}, status=409)

        listing.refresh_from_db()
        return Response(StaffDealerListingSerializer(listing).data)


class StaffDealerDocumentView(APIView):
    """Hand over one document, to somebody we have checked first.

    Paperwork never goes through MEDIA. A logbook names a registered owner and
    an ID is an ID, so the bytes are streamed from here after the caller has
    been authenticated - the file path is not a credential, and treating it as
    one is how a media directory becomes a data leak.

    Sales as well as managers: an agent working a dealer ticket has to be able
    to read what was sent, and the decision itself is still a manager's.
    """

    permission_classes = [IsSales]

    def get(self, request, pk):
        document = (
            DealerDocument.objects.select_related("application")
            .filter(pk=pk)
            .first()
        )
        if document is None:
            raise Http404

        try:
            handle = document.file.open("rb")
        except (FileNotFoundError, ValueError):
            # The row can outlive the file on an ephemeral filesystem. Say so
            # plainly rather than serving a 500.
            return Response(
                {"error": "that file is no longer on disk"}, status=410
            )

        # as_attachment: a logbook opening inline in a browser tab is a logbook
        # sitting in somebody's history and cache.
        return FileResponse(handle, as_attachment=True, filename=document.filename)
