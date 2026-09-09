"""Resetting a forgotten password, and changing a remembered one.

Signed tokens rather than a model, matching `verification.py` - there is no
row to clean up and no table to leak. The difference from that module is that
a verification link is harmless to replay and a reset link is not, so this one
has to die the moment it is used.

It does that without storing anything: the token carries a fingerprint of the
password hash and the last login time it was minted against. Setting a new
password changes the hash, and signing in changes the login time; either one
changes the fingerprint, which makes every outstanding link for that account
fail the comparison. So a link dies when it is used, and also when the real
owner simply logs in - which is the desired answer to "somebody requested a
reset on my account and I did not". This is the same trick as Django's own
`PasswordResetTokenGenerator`, spelled out here because the rest of the app's
token handling is spelled out too.
"""

import hashlib
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing

from .mail import send as send_mail

logger = logging.getLogger("goldride")

SALT = "goldride.password-reset"


class ResetError(Exception):
    """Safe to show a user."""


def _fingerprint(user):
    """A short digest of the stored password hash.

    The hash itself never goes into a token that travels by email. It is
    already a hash, but it is also the single most sensitive column on the
    row, and a signed token is readable by anybody holding it - `signing`
    signs, it does not encrypt.
    """
    basis = f"{user.password}{user.last_login or ''}"
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def make_token(user):
    return signing.dumps(
        {"uid": user.pk, "email": user.email, "fp": _fingerprint(user)},
        salt=SALT,
    )


def read_token(token):
    """The user this token is for, or a ResetError explaining why not."""
    try:
        payload = signing.loads(
            token,
            salt=SALT,
            max_age=settings.PASSWORD_RESET_TIMEOUT,
        )
    except signing.SignatureExpired:
        raise ResetError("That link has expired. Ask for a new one.")
    except signing.BadSignature:
        raise ResetError("That link is not valid.")

    if not isinstance(payload, dict) or "uid" not in payload:
        raise ResetError("That link is not valid.")

    try:
        user = get_user_model().objects.get(pk=payload["uid"])
    except get_user_model().DoesNotExist:
        # Same message as a bad signature: whether an account still exists is
        # not something a link-holder is owed.
        raise ResetError("That link is not valid.")

    if not user.is_active:
        raise ResetError("That link is not valid.")

    # The address moved on, so this link was sent somewhere that is no longer
    # the account's - exactly the case verification.py guards too.
    if (payload.get("email") or "").lower() != (user.email or "").lower():
        raise ResetError("That link was sent to a different address.")

    # Already used, or the password changed some other way since it was sent.
    if payload.get("fp") != _fingerprint(user):
        raise ResetError("That link has already been used. Ask for a new one.")

    return user


def send_reset_email(user):
    """Mail a reset link. Returns False when there is nowhere to send it."""
    if not user.email:
        return False

    link = f"{settings.FRONTEND_URL}/reset-password/{make_token(user)}"
    hours = settings.PASSWORD_RESET_TIMEOUT // 3600

    send_mail(
        subject="Reset your Goldride Motors password",
        message=(
            f"Hello {user.first_name or user.username},\n\n"
            "Somebody asked to reset the password on this account. Open this "
            f"link to choose a new one:\n\n{link}\n\n"
            f"The link works once and expires in {hours} hours.\n\n"
            "If this was not you, ignore this email. Your password has not "
            "changed and nothing happens until the link is opened.\n"
        ),
        to=[user.email],
    )
    return True


def revoke_sessions(user):
    """Drop every API token this account holds.

    A password is reset precisely when somebody may have had it. Leaving the
    old auth tokens alive would let whoever took the account keep it - DRF
    tokens do not expire on their own, so nothing else would ever evict them.
    """
    from rest_framework.authtoken.models import Token

    deleted, _ = Token.objects.filter(user=user).delete()
    if deleted:
        logger.info("Revoked %s API token(s) for user %s", deleted, user.pk)
    return deleted


def set_password(user, raw_password):
    """Apply a new password and evict everything holding the old one."""
    user.set_password(raw_password)
    user.save(update_fields=["password"])
    revoke_sessions(user)
    logger.info("Password changed for user %s", user.pk)
    return user
