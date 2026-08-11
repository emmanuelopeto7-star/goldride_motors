import logging
import re
import secrets

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from .models import SocialAccount, get_profile

logger = logging.getLogger(__name__)

User = get_user_model()

LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


class SocialAuthError(Exception):
    """Safe to show a user. Detail goes to the log, not the response."""


class EmailInUse(Exception):
    """The address is on an account nobody has ever proved they own.

    Deliberately not a SocialAuthError: this is not a failed sign-in, it is a
    refusal to join two identities that have not been shown to be the same
    person. The caller turns it into a 409 the frontend can branch on.
    """

    code = "email_in_use"


def verify_google(credential):
    if not settings.GOOGLE_CLIENT_ID:
        raise SocialAuthError("Google sign-in is not available")

    try:
        claims = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        logger.warning("Google credential rejected: %s", exc)
        raise SocialAuthError("Could not sign you in with Google") from exc

    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        logger.warning("Google token had unexpected issuer: %s", claims.get("iss"))
        raise SocialAuthError("Could not sign you in with Google")

    return {
        "uid": claims["sub"],
        "email": claims.get("email", ""),
        "email_verified": bool(claims.get("email_verified")),
        "first_name": claims.get("given_name", ""),
        "last_name": claims.get("family_name", ""),
    }


def verify_linkedin(code):
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise SocialAuthError("LinkedIn sign-in is not available")

    resp = requests.post(
        LINKEDIN_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            # Never taken from the caller - it must match what was registered.
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    try:
        payload = resp.json()
    except ValueError:
        logger.warning("LinkedIn token endpoint returned HTTP %s", resp.status_code)
        raise SocialAuthError("Could not sign you in with LinkedIn")

    access_token = payload.get("access_token")
    if not access_token:
        logger.warning("LinkedIn refused the code: %s", payload.get("error_description"))
        raise SocialAuthError("Could not sign you in with LinkedIn")

    resp = requests.get(
        LINKEDIN_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )

    try:
        profile = resp.json()
    except ValueError:
        logger.warning("LinkedIn userinfo returned HTTP %s", resp.status_code)
        raise SocialAuthError("Could not sign you in with LinkedIn")

    if not profile.get("sub"):
        logger.warning("LinkedIn userinfo had no sub")
        raise SocialAuthError("Could not sign you in with LinkedIn")

    return {
        "uid": profile["sub"],
        "email": profile.get("email", ""),
        "email_verified": bool(profile.get("email_verified")),
        "first_name": profile.get("given_name", ""),
        "last_name": profile.get("family_name", ""),
    }


def _username_base(email, uid):
    base = re.sub(r"[^a-zA-Z0-9_.-]", "", (email or "").split("@")[0])
    return (base or f"user{uid[:8]}")[:24] or "user"


def create_user_unique(base, email, first_name="", last_name="", password=None):
    """Create a user, surviving a race on the username.

    Registration reuses this whenever the caller left the username out, so
    a derived name gets the same collision handling a social sign-in gets.
    """
    for attempt in range(6):
        username = base if attempt == 0 else f"{base}-{secrets.token_hex(3)}"
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                )
        except IntegrityError:
            continue
    raise SocialAuthError("Could not create your account, please try again")


@transaction.atomic
def get_or_create_social_user(provider, profile):
    uid = profile["uid"]
    claimed_email = (profile.get("email") or "").strip()
    verified = bool(profile.get("email_verified")) and bool(claimed_email)

    existing = SocialAccount.objects.filter(provider=provider, uid=uid).first()
    if existing:
        return existing.user, False

    user = None
    if verified:
        # Only ever link when the provider vouches for the address.
        user = User.objects.filter(email__iexact=claimed_email).first()

        if user is not None and not get_profile(user).email_verified:
            # Nothing ever proved that account owns the address - registration
            # certainly did not - so the two identities cannot be assumed to
            # be the same person. Linking here would hand this sign-in to
            # whoever typed the address first.
            logger.warning(
                "Refused to link %s sign-in to unverified account %s",
                provider,
                user.pk,
            )
            raise EmailInUse(claimed_email)

    created = False
    if user is None:
        # An unverified address is never written to the user record: two
        # accounts must not end up holding one email, and doing so would
        # also lock the real owner out of registering with a password.
        user = create_user_unique(
            # An unverified address must not reserve the username derived
            # from it either, or the real owner is squatted out.
            base=_username_base(claimed_email if verified else "", uid),
            email=claimed_email if verified else "",
            first_name=profile.get("first_name", ""),
            last_name=profile.get("last_name", ""),
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])

        if verified:
            # The provider vouched for it, so this account may be linked to
            # in future - it is the one kind of account that has been proven.
            user_profile = get_profile(user)
            user_profile.email_verified = True
            user_profile.save(update_fields=["email_verified"])

        group, _ = Group.objects.get_or_create(name="Customer")
        user.groups.add(group)
        created = True

    # get_or_create, not create: two first-time logins for the same account
    # can both miss the lookup above and race to insert.
    SocialAccount.objects.get_or_create(
        provider=provider,
        uid=uid,
        defaults={"email": claimed_email, "user": user},
    )
    return user, created
