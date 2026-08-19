"""Proving an address belongs to whoever typed it.

No model and no migration: the link carries a signed payload instead of a
row. A token is only good for the address it was issued for, so changing
the email invalidates every outstanding link automatically.
"""
import logging

from django.conf import settings

from .mail import send as send_mail
from django.core import signing

from .models import get_profile

logger = logging.getLogger(__name__)

SALT = "goldride.email-verify"


class VerificationError(Exception):
    """Safe to show a user."""


def make_token(user):
    # The email is inside the payload, not just the user id: a link mailed
    # to the old address must not verify a new one.
    return signing.dumps(
        {"uid": user.pk, "email": user.email},
        salt=SALT,
    )


def read_token(token):
    try:
        payload = signing.loads(
            token,
            salt=SALT,
            max_age=settings.EMAIL_VERIFICATION_TIMEOUT,
        )
    except signing.SignatureExpired:
        raise VerificationError("That link has expired. Ask for a new one.")
    except signing.BadSignature:
        raise VerificationError("That link is not valid.")

    if not isinstance(payload, dict) or "uid" not in payload:
        raise VerificationError("That link is not valid.")
    return payload


def send_verification_email(user):
    """No-op for an account with no address - social sign-ins arrive that way."""
    if not user.email:
        return False

    link = f"{settings.SITE_URL.rstrip('/')}/api/auth/verify-email/{make_token(user)}/"

    send_mail(
        subject="Confirm your email address",
        message=(
            f"Hello {user.first_name or user.username},\n\n"
            "Confirm this address to finish setting up your Goldride Motors "
            f"account:\n\n{link}\n\n"
            "If you did not create an account, ignore this email - nothing "
            "happens until the link is opened.\n"
        ),
        to=[user.email],
        # A dead mail server must not turn a signup into a 500. The address
        # stays unverified, and /api/auth/verify-email/resend/ tries again.
    )
    return True


def confirm(token):
    """Mark the address proved. Returns the user."""
    from django.contrib.auth import get_user_model

    payload = read_token(token)

    try:
        user = get_user_model().objects.get(pk=payload["uid"])
    except get_user_model().DoesNotExist:
        raise VerificationError("That link is not valid.")

    # The address moved on since the link was sent, so this proves nothing
    # about where the account is now.
    if (payload.get("email") or "").lower() != (user.email or "").lower():
        raise VerificationError(
            "That link was sent to a different address. Ask for a new one."
        )

    profile = get_profile(user)
    if not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
        logger.info("Email verified for user %s", user.pk)

    return user
