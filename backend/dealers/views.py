"""The two doors a dealer uses: applying, and running their own listings.

Each opens one way, per the standing rule about public endpoints. Applying is
**write-only** - a list view here would hand anybody the name, phone number and
email of every dealership that has ever approached us, which is a competitor's
prospect list. Activation reads a signed token and nothing else.

Inside the portal, every queryset is scoped to `request.user.dealer` before
anything else happens, and somebody else's listing is a **404, never a 403**:
the id is in the URL and guessable, so "not yours" and "does not exist" have to
be indistinguishable. Same rule as the chat threads.
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from goldride_app.permissions import IsDealer

from .activation import ActivationError, read_token
from .models import (
    DealerDocument,
    DealerListing,
    DealerListingImage,
)
from .serializers import (
    APPLICATION_CAR_FIELDS,
    MAX_APPLICATION_DOCUMENTS,
    MAX_APPLICATION_PHOTOS,
    DealerApplicationCreateSerializer,
    DealerListingImageSerializer,
    DealerListingSerializer,
    DealerSerializer,
)
from .services import announce_application


class DealerApplyView(generics.CreateAPIView):
    """Anybody may ask. Nobody may read the answers back.

    One multipart submission carries the dealership, the first car they want
    listed, its photographs and the paperwork behind it - because that is one
    errand, and because staff deciding whether to take a dealership on should
    be looking at an actual car rather than a promise of one.

    It is an unauthenticated upload path, so the counts are capped here and the
    per-file size and type are capped on the model. Everything lands in one
    transaction: a half-written application with photographs and no car is
    worse than a refusal, because nobody would know to look at it.
    """

    serializer_class = DealerApplicationCreateSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "dealers"
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        payload = _flatten_car(request.data)

        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        car = serializer.validated_data.pop("car")

        photos = request.FILES.getlist("photos")
        documents = request.FILES.getlist("documents")
        # Parallel to `documents`, one label per file. Short is fine - anything
        # unlabelled is "other" - but the pairing has to be positional because
        # multipart has no other way to associate the two.
        kinds = request.data.getlist("document_kinds") if hasattr(
            request.data, "getlist"
        ) else []

        if len(photos) > MAX_APPLICATION_PHOTOS:
            raise ValidationError(
                {"photos": [f"Attach at most {MAX_APPLICATION_PHOTOS} photographs."]}
            )
        if len(documents) > MAX_APPLICATION_DOCUMENTS:
            raise ValidationError(
                {"documents": [f"Attach at most {MAX_APPLICATION_DOCUMENTS} files."]}
            )

        _require_paperwork(serializer.validated_data.get("seller_type"), kinds)

        with transaction.atomic():
            application = serializer.save()
            listing = DealerListing.objects.create(application=application, **car)

            for photo in photos:
                DealerListingImage.objects.create(listing=listing, image=photo)

            valid_kinds = {key for key, _label in DealerDocument.KIND_CHOICES}
            for index, upload in enumerate(documents):
                kind = kinds[index] if index < len(kinds) else DealerDocument.OTHER
                document = DealerDocument(
                    application=application,
                    kind=kind if kind in valid_kinds else DealerDocument.OTHER,
                    file=upload,
                )
                try:
                    # full_clean so the model's size and type validators run: a
                    # serializer FileField alone would take anything.
                    document.full_clean(exclude=["application"])
                except DjangoValidationError as problem:
                    # Translated rather than allowed to propagate: a Django
                    # ValidationError escaping a DRF view is a 500, and a
                    # public form answering "server error" to a file that is
                    # simply too large tells the sender nothing they can act on.
                    raise ValidationError(
                        {"documents": problem.messages}
                    ) from problem
                document.save()

        # The ticket is raised by a signal; this only tells the office.
        announce_application(application)

        return Response(
            self.get_serializer(application).data, status=status.HTTP_201_CREATED
        )


def _require_paperwork(seller_type, kinds):
    """Refuse an application that is missing paperwork it cannot proceed without.

    Checked here rather than left to staff to chase: a dealership without a
    trade licence or an owner without a logbook is not a decision anybody can
    make, and finding that out a day later by email wastes both sides' time.

    The message names every missing document at once. Refusing one at a time
    would mean a dealership resubmits seven times to learn seven things.
    """
    required = DealerDocument.required_for(seller_type)
    labels = dict(DealerDocument.KIND_CHOICES)
    attached = set(kinds)

    missing = [labels[kind] for kind in required if kind not in attached]
    if missing:
        raise ValidationError(
            {
                "documents": [
                    "We still need: " + ", ".join(missing) + "."
                ]
            }
        )


def _flatten_car(data):
    """Gather `car_make`, `car_year`… into the nested `car` the serializer wants.

    Multipart has no notion of nesting, and a browser form posting
    `car[make]` is a convention every framework spells differently. A prefix
    is the one shape that survives a plain `<form>`, `FormData` and a JSON
    body alike - and a JSON caller may still send `car` as an object, which is
    passed through untouched.
    """
    if not hasattr(data, "getlist"):
        return data

    payload = {}
    car = {}
    for key in data.keys():
        if key in ("photos", "documents", "document_kinds"):
            continue
        value = data.get(key)
        if key.startswith("car_"):
            field = key[4:]
            if field in APPLICATION_CAR_FIELDS and value not in ("", None):
                car[field] = value
        else:
            payload[key] = value

    payload["car"] = car if car else data.get("car", {})
    return payload


class DealerActivateView(APIView):
    """Set the password on an approved dealer account.

    Open by necessity - the whole point is that they cannot sign in yet - and
    safe because the token is signed, expires, and carries the current password
    hash, so it stops working the moment it is used once.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "dealers"

    @extend_schema(
        request=inline_serializer(
            name="DealerActivation",
            fields={"password": serializers.CharField()},
        ),
        responses={200: inline_serializer(
            name="DealerActivated",
            fields={"detail": serializers.CharField()},
        )},
    )
    def post(self, request, token):
        try:
            user = read_token(token)
        except ActivationError as problem:
            return Response({"detail": str(problem)}, status=400)

        password = request.data.get("password") or ""
        try:
            validate_password(password, user)
        except DjangoValidationError as problem:
            return Response({"password": list(problem.messages)}, status=400)

        user.set_password(password)
        user.save(update_fields=["password"])
        return Response({"detail": "Your password is set. You can sign in now."})

    def get(self, request, token):
        """Whether the link is still good, so the page can say so up front."""
        try:
            user = read_token(token)
        except ActivationError as problem:
            return Response({"detail": str(problem)}, status=400)
        return Response({"email": user.email, "name": user.first_name})


class DealerMeView(generics.RetrieveUpdateAPIView):
    """The signed-in dealership. They may correct their own contact details."""

    serializer_class = DealerSerializer
    permission_classes = [IsDealer]

    def get_object(self):
        return self.request.user.dealer


class DealerListingListView(generics.ListCreateAPIView):
    serializer_class = DealerListingSerializer
    permission_classes = [IsDealer]

    def get_queryset(self):
        queryset = self.request.user.dealer.listings.prefetch_related("images")
        state = self.request.query_params.get("status")
        if state:
            queryset = queryset.filter(status=state)
        return queryset

    def perform_create(self, serializer):
        # The dealer is taken from the account, never from the request body -
        # otherwise a dealer could file a car under a competitor's name.
        serializer.save(dealer=self.request.user.dealer)


class DealerListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DealerListingSerializer
    permission_classes = [IsDealer]

    def get_queryset(self):
        return self.request.user.dealer.listings.prefetch_related("images")

    def update(self, request, *args, **kwargs):
        listing = self.get_object()
        if not listing.is_editable:
            return Response(
                {"error": f"a {listing.status} submission cannot be edited"},
                status=400,
            )
        # Editing a rejected car is how it gets resubmitted: back into the
        # queue, with the old decision cleared so staff see a fresh one.
        response = super().update(request, *args, **kwargs)
        if listing.status == DealerListing.REJECTED:
            listing.refresh_from_db()
            listing.status = DealerListing.SUBMITTED
            listing.decision_note = ""
            listing.reviewed_by = None
            listing.reviewed_at = None
            listing.save(
                update_fields=[
                    "status", "decision_note", "reviewed_by", "reviewed_at",
                ]
            )
            response.data = DealerListingSerializer(listing).data
        return response

    def destroy(self, request, *args, **kwargs):
        """Withdrawing, not deleting.

        A submission staff have already read is part of the record of what was
        offered; and one that became a listing must not take its own history
        with it. Withdrawn ones simply leave the queue.
        """
        listing = self.get_object()
        if listing.status == DealerListing.APPROVED:
            return Response(
                {"error": "this car is already on the site - ask us to take it down"},
                status=400,
            )
        listing.status = DealerListing.WITHDRAWN
        listing.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class DealerListingImageView(generics.CreateAPIView):
    serializer_class = DealerListingImageSerializer
    permission_classes = [IsDealer]

    def create(self, request, pk):
        listing = (
            request.user.dealer.listings.filter(pk=pk).first()
        )
        # 404 rather than 403: the id is guessable, so somebody else's listing
        # must look exactly like one that was never there.
        if listing is None:
            return Response({"detail": "Not found."}, status=404)
        if not listing.is_editable:
            return Response(
                {"error": f"a {listing.status} submission cannot be edited"},
                status=400,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(listing=listing)
        return Response(serializer.data, status=201)


class DealerListingImageDetailView(APIView):
    permission_classes = [IsDealer]

    def delete(self, request, pk, image_id):
        listing = request.user.dealer.listings.filter(pk=pk).first()
        if listing is None:
            return Response({"detail": "Not found."}, status=404)
        if not listing.is_editable:
            return Response(
                {"error": f"a {listing.status} submission cannot be edited"},
                status=400,
            )

        photo = DealerListingImage.objects.filter(pk=image_id, listing=listing).first()
        if photo is None:
            return Response({"detail": "Not found."}, status=404)

        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
