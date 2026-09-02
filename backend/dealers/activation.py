"""Handing a new dealer their account without ever mailing them a password.

Approval creates the account, but nobody here knows what its password should
be - and a generated one sent by email is a password sitting in an inbox
forever. So the account is created with an unusable password and the dealer is
sent a signed link that lets them set one.

Signed payload, no model and no migration, the same as email verification. The
user id and the current password hash are both inside it, so the link dies the
moment a password exists: following an old activation link cannot reset an
account somebody is already using.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing

from goldride_app.mail import send as send_mail

logger = logging.getLogger(__name__)

User = get_user_model()

SALT = "goldride.dealer-activate"


class ActivationError(Exception):
    """Safe to show a user."""


def make_token(user):
    return signing.dumps(
        {"uid": user.pk, "pw": user.password},
        salt=SALT,
    )


def read_token(token):
    """Return the user this token activates, or raise with a readable reason."""
    try:
        payload = signing.loads(
            token,
            salt=SALT,
            max_age=settings.DEALER_ACTIVATION_TIMEOUT,
        )
    except signing.SignatureExpired:
        raise ActivationError("That link has expired. Ask us for a new one.")
    except signing.BadSignature:
        raise ActivationError("That link is not valid.")

    if not isinstance(payload, dict) or "uid" not in payload:
        raise ActivationError("That link is not valid.")

    user = User.objects.filter(pk=payload["uid"]).first()
    if user is None or not user.is_active:
        raise ActivationError("That link is not valid.")

    # The hash is part of the signature, so the first successful use - which
    # changes the hash - invalidates every other copy of the link.
    if user.password != payload.get("pw"):
        raise ActivationError(
            "That link has already been used. Sign in, or reset your password."
        )

    return user


def activation_link(user):
    return f"{settings.FRONTEND_URL.rstrip('/')}/dealer/activate/{make_token(user)}"


def send_activation_email(dealer, published=None):
    """Tell an approved dealership how to get in. Never raises.

    `published` is whatever went live with the approval - the car they
    applied with. Saying so matters: it is already on the site by the time
    they read this, and stumbling across it later is not how anybody wants
    to learn their car is being advertised.
    """
    user = dealer.user
    if not user.email:
        logger.warning("Dealer %s has no address to activate", dealer.pk)
        return False

    listed = ""
    if published:
        cars = "\n".join(f"  - {car}" for car in published)
        listed = f"\nAlready live on the site:\n\n{cars}\n"

    return send_mail(
        subject="Your Goldride dealer account",
        message=(
            f"{dealer.contact_name},\n\n"
            f"{dealer.name} has been approved to list cars on Goldride.\n"
            f"{listed}\n"
            "Set your password and sign in here:\n\n"
            f"{activation_link(user)}\n\n"
            "The link is good for seven days. Once you are in, you can submit "
            "more cars and follow what has been approved.\n\n"
            "Goldride Motors"
        ),
        to=user.email,
    )
