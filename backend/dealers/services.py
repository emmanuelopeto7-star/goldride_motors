"""Every decision about a dealer, made once.

The rule this file exists for is the one the ticket system was built around: a
request must never get two answers. Two managers looking at the same
application would otherwise both approve it, and approving twice here does not
just send two emails - it creates two accounts for one dealership, or two
listings for one car.

So every decision is a conditional read under `select_for_update()`, exactly
as `purchases.services` does it: the row is locked, its status is re-read
inside the transaction, and the second caller finds it already decided.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from goldride_app.mail import send as send_mail
from goldride_app.social import _username_base, create_user_unique

from .activation import send_activation_email
from .models import Dealer, DealerApplication, DealerListing

logger = logging.getLogger(__name__)

User = get_user_model()

DEALER_GROUP = "Dealer"


def approve_application(application, reviewed_by, note=""):
    """Say yes: create the dealership, list the car they applied with, invite them.

    One decision, not three. Staff have the car, its photographs and its
    paperwork in front of them while deciding whether to take the dealership
    on, so approving is also approving that car - asking them to review the
    same evidence twice would be theatre.

    The publish happens inside the same transaction and under the same lock as
    the status change. Two managers clicking together would otherwise create
    two accounts *and* two listings for one physical car.

    Returns (dealer, ok, message). `dealer.published_cars` carries whatever
    went live, for the caller to report.
    """
    with transaction.atomic():
        locked_status = (
            DealerApplication.objects.select_for_update()
            .filter(pk=application.pk)
            .values_list("status", flat=True)
            .first()
        )
        if locked_status is None:
            return None, False, "that application no longer exists"
        if locked_status != DealerApplication.PENDING:
            return None, False, "this application has already been reviewed"

        # An address that already has an account is not ours to claim. Linking
        # it silently would hand this dealership somebody else's login, which
        # is the same hole social sign-in was closed against - so a person
        # decides instead. See decision 9 in the security notes.
        if User.objects.filter(email__iexact=application.email).exists():
            return (
                None,
                False,
                "an account already uses that email address - sort out which "
                "account this dealership should sign in with before approving",
            )

        user = create_user_unique(
            base=_username_base(application.email, str(application.pk)),
            email=application.email,
            first_name=application.contact_name[:150],
        )
        # No password anybody knows, including us. The activation link is how
        # one gets set; until then the account cannot be signed into.
        user.set_unusable_password()
        user.save(update_fields=["password"])

        Group.objects.get_or_create(name=DEALER_GROUP)[0].user_set.add(user)

        dealer = Dealer.objects.create(
            user=user,
            application=application,
            seller_type=application.seller_type,
            # The trading name for a dealership, the person's name for a
            # private seller - one property so nothing downstream disagrees.
            name=application.display_name,
            contact_name=application.contact_name,
            phone=application.phone,
            location=application.location,
        )

        # The cars they applied with now belong to a dealership that exists.
        # `application` is left in place: it is the record of what was reviewed.
        published = []
        for listing in application.listings.filter(
            status=DealerListing.SUBMITTED
        ).select_for_update():
            listing.dealer = dealer
            listing.save(update_fields=["dealer"])

            car, message = listing.publish()
            if car is None:
                # Nothing here should be able to fail, but a half-listed
                # application is worse than a refused one: undo the lot and
                # let a person look at it.
                transaction.set_rollback(True)
                return None, False, f"could not list their car - {message}"

            listing.status = DealerListing.APPROVED
            listing.reviewed_by = reviewed_by
            listing.reviewed_at = timezone.now()
            listing.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            published.append(car)

        application.status = DealerApplication.APPROVED
        application.decision_note = note[:200]
        application.reviewed_by = reviewed_by
        application.reviewed_at = timezone.now()
        application.save(
            update_fields=["status", "decision_note", "reviewed_by", "reviewed_at"]
        )

    # Outside the transaction: a mail server being slow should not hold a row
    # lock, and a mail server being down must not undo an approval.
    dealer.published_cars = published
    send_activation_email(dealer, published=published)
    return dealer, True, "approved"


def reject_application(application, reviewed_by, note=""):
    with transaction.atomic():
        locked_status = (
            DealerApplication.objects.select_for_update()
            .filter(pk=application.pk)
            .values_list("status", flat=True)
            .first()
        )
        if locked_status is None:
            return False, "that application no longer exists"
        if locked_status != DealerApplication.PENDING:
            return False, "this application has already been reviewed"

        application.status = DealerApplication.REJECTED
        application.decision_note = note[:200]
        application.reviewed_by = reviewed_by
        application.reviewed_at = timezone.now()
        application.save(
            update_fields=["status", "decision_note", "reviewed_by", "reviewed_at"]
        )

    send_mail(
        subject="Your Goldride listing application",
        message=(
            f"{application.contact_name},\n\n"
            "Thank you for asking to list with Goldride Motors. We are not "
            "able to take this on at the moment.\n\n"
            + (f"{note}\n\n" if note else "")
            + "Goldride Motors"
        ),
        to=application.email,
    )
    return True, "rejected"


def approve_listing(listing, reviewed_by, note=""):
    """Put a dealer's car on the site.

    Returns (car, ok, message). The status check and the publish happen under
    the same lock, so two managers cannot create two listings for one car.
    """
    with transaction.atomic():
        locked = (
            DealerListing.objects.select_for_update()
            .filter(pk=listing.pk)
            .first()
        )
        if locked is None:
            return None, False, "that submission no longer exists"
        if locked.status != DealerListing.SUBMITTED:
            return None, False, f"this submission is already {locked.status}"

        car, message = locked.publish()
        if car is None:
            return None, False, message

        locked.status = DealerListing.APPROVED
        locked.decision_note = note[:200]
        locked.reviewed_by = reviewed_by
        locked.reviewed_at = timezone.now()
        locked.save(
            update_fields=["status", "decision_note", "reviewed_by", "reviewed_at"]
        )
        dealer = locked.dealer

    send_mail(
        subject=f"Listed: {listing.year} {listing.make} {listing.model}",
        message=(
            f"{dealer.contact_name},\n\n"
            f"The {listing.year} {listing.make} {listing.model} you submitted "
            "is now live on goldridemotors.co.ke.\n\n"
            "Goldride Motors"
        ),
        to=dealer.user.email,
    )
    return car, True, "listed"


def reject_listing(listing, reviewed_by, note=""):
    with transaction.atomic():
        locked_status = (
            DealerListing.objects.select_for_update()
            .filter(pk=listing.pk)
            .values_list("status", flat=True)
            .first()
        )
        if locked_status is None:
            return False, "that submission no longer exists"
        if locked_status != DealerListing.SUBMITTED:
            return False, f"this submission is already {locked_status}"

        listing.status = DealerListing.REJECTED
        listing.decision_note = note[:200]
        listing.reviewed_by = reviewed_by
        listing.reviewed_at = timezone.now()
        listing.save(
            update_fields=["status", "decision_note", "reviewed_by", "reviewed_at"]
        )

    send_mail(
        subject=f"Not listed: {listing.year} {listing.make} {listing.model}",
        message=(
            f"{listing.dealer.contact_name},\n\n"
            f"We have not listed the {listing.year} {listing.make} "
            f"{listing.model} you submitted.\n\n"
            + (f"{note}\n\n" if note else "")
            + "You can edit it and send it again from your dealer area.\n\n"
            "Goldride Motors"
        ),
        to=listing.dealer.user.email,
    )
    return True, "rejected"


def announce_application(application):
    """Tell the office somebody has asked to list a car. Never raises."""
    if application.is_dealership:
        identity = f"Fleet: {application.fleet_size or 'not stated'}"
    else:
        identity = f"ID: {application.id_number or 'not given'}"

    send_mail(
        subject=f"Listing application: {application.display_name}",
        message=(
            f"{application.display_name} ({application.location}) has asked to "
            "list a car on Goldride, as a "
            f"{application.get_seller_type_display().lower()}.\n\n"
            f"Contact: {application.contact_name}, {application.phone}, "
            f"{application.email}\n"
            f"{identity}\n\n"
            f"{application.message}\n\n"
            "It is in the staff queue."
        ),
        to=[settings.SALES_EMAIL],
    )
