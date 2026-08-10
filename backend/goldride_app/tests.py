from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import SocialAccount
from .social import SocialAuthError

User = get_user_model()

GOOGLE = "/api/auth/social/google/"
LINKEDIN = "/api/auth/social/linkedin/"


def profile(uid, email="", verified=False, first="", last=""):
    return {
        "uid": uid,
        "email": email,
        "email_verified": verified,
        "first_name": first,
        "last_name": last,
    }


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.TokenAuthentication",
        ],
    }
)
class SocialLoginTests(APITestCase):
    """Throttling is off here so the rules themselves are what's under test."""

    def test_unknown_provider_is_rejected(self):
        response = self.client.post(
            "/api/auth/social/facebook/", {"credential": "x"}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_google_without_a_credential_is_rejected(self):
        response = self.client.post(GOOGLE, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_linkedin_without_a_code_is_rejected(self):
        response = self.client.post(LINKEDIN, {}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("goldride_app.views.verify_google")
    def test_provider_failure_does_not_leak_internals(self, verify):
        verify.side_effect = SocialAuthError("Could not sign you in with Google")

        response = self.client.post(GOOGLE, {"credential": "forged"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"], "Could not sign you in with Google"
        )
        self.assertNotIn("Traceback", str(response.content))

    @patch("goldride_app.views.verify_google")
    def test_new_user_is_created_as_a_customer(self, verify):
        verify.return_value = profile(
            "g-1", "amina@example.com", verified=True, first="Amina", last="Otieno"
        )

        response = self.client.post(GOOGLE, {"credential": "ok"}, format="json")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["created"])
        self.assertTrue(body["token"])
        self.assertEqual(body["roles"], ["Customer"])

        user = User.objects.get(email="amina@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.first_name, "Amina")

    @patch("goldride_app.views.verify_google")
    def test_signing_in_twice_does_not_duplicate(self, verify):
        verify.return_value = profile("g-1", "amina@example.com", verified=True)

        first = self.client.post(GOOGLE, {"credential": "ok"}, format="json").json()
        second = self.client.post(GOOGLE, {"credential": "ok"}, format="json").json()

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["token"], second["token"])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.count(), 1)

    @patch("goldride_app.views.verify_google")
    def test_verified_email_links_to_an_existing_account(self, verify):
        existing = User.objects.create_user(
            "mwangi", email="mwangi@example.com", password="Sh1llings!2026"
        )
        verify.return_value = profile("g-2", "mwangi@example.com", verified=True)

        body = self.client.post(GOOGLE, {"credential": "ok"}, format="json").json()

        self.assertFalse(body["created"])
        self.assertEqual(body["username"], "mwangi")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(existing.social_accounts.count(), 1)

    @patch("goldride_app.views.verify_linkedin")
    def test_unverified_email_cannot_take_over_an_account(self, verify):
        User.objects.create_user(
            "mwangi", email="mwangi@example.com", password="Sh1llings!2026"
        )
        verify.return_value = profile("li-9", "mwangi@example.com", verified=False)

        body = self.client.post(LINKEDIN, {"code": "abc"}, format="json").json()

        self.assertNotEqual(body["username"], "mwangi")
        self.assertTrue(body["created"])

    @patch("goldride_app.views.verify_linkedin")
    def test_unverified_email_is_not_written_to_the_user(self, verify):
        """Otherwise two accounts share an address and the owner can never register."""
        verify.return_value = profile("li-9", "stolen@example.com", verified=False)

        body = self.client.post(LINKEDIN, {"code": "abc"}, format="json").json()

        user = User.objects.get(username=body["username"])
        self.assertEqual(user.email, "")
        self.assertEqual(
            User.objects.filter(email="stolen@example.com").count(), 0
        )
        # the claim is still recorded against the link itself
        self.assertEqual(user.social_accounts.first().email, "stolen@example.com")

    @patch("goldride_app.views.verify_linkedin")
    def test_the_real_owner_can_still_register_afterwards(self, verify):
        verify.return_value = profile("li-9", "owner@example.com", verified=False)
        squatter = self.client.post(LINKEDIN, {"code": "abc"}, format="json").json()

        # the unverified claim reserves neither the email nor the username
        self.assertNotEqual(squatter["username"], "owner")

        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "owner",
                "email": "owner@example.com",
                "first_name": "Owner",
                "password": "Sh1llings!2026",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

    @patch("goldride_app.views.verify_google")
    def test_username_collision_gets_a_suffix(self, verify):
        User.objects.create_user("amina", email="someone.else@example.com")
        verify.return_value = profile("g-3", "amina@example.com", verified=True)

        body = self.client.post(GOOGLE, {"credential": "ok"}, format="json").json()

        self.assertNotEqual(body["username"], "amina")
        self.assertTrue(body["username"].startswith("amina-"))

    @patch("goldride_app.views.verify_google")
    def test_disabled_accounts_cannot_sign_in(self, verify):
        user = User.objects.create_user("banned", email="banned@example.com")
        user.is_active = False
        user.save()
        SocialAccount.objects.create(provider="google", uid="g-4", user=user)
        verify.return_value = profile("g-4", "banned@example.com", verified=True)

        response = self.client.post(GOOGLE, {"credential": "ok"}, format="json")

        self.assertEqual(response.status_code, 403)

    @patch("goldride_app.views.verify_google")
    def test_the_token_actually_works(self, verify):
        verify.return_value = profile("g-5", "amina@example.com", verified=True)
        token = self.client.post(GOOGLE, {"credential": "ok"}, format="json").json()["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["roles"], ["Customer"])


class SocialAccountModelTests(APITestCase):
    def test_one_uid_per_provider(self):
        from django.db import IntegrityError, transaction

        user = User.objects.create_user("a", email="a@example.com")
        other = User.objects.create_user("b", email="b@example.com")
        SocialAccount.objects.create(provider="google", uid="dup", user=user)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SocialAccount.objects.create(provider="google", uid="dup", user=other)

    def test_same_uid_on_different_providers_is_allowed(self):
        user = User.objects.create_user("a", email="a@example.com")
        SocialAccount.objects.create(provider="google", uid="same", user=user)
        SocialAccount.objects.create(provider="linkedin", uid="same", user=user)

        self.assertEqual(user.social_accounts.count(), 2)
