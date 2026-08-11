from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.contrib.auth.models import Group
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from cars.models import Car
from purchases.models import PurchaseRequest

from .models import SocialAccount, get_profile
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


def verify_account(user):
    """Mark an account's address as proved, the way a provider would."""
    user_profile = get_profile(user)
    user_profile.email_verified = True
    user_profile.save(update_fields=["email_verified"])
    return user


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.TokenAuthentication",
        ],
    }
)
class SocialLoginTests(APITestCase):
    """DRF binds throttle rates at import, so the bucket is cleared instead."""

    def setUp(self):
        cache.clear()

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
        # The good path needs an account whose address was actually proved -
        # without this the sign-in is refused, which is the point of the fix.
        verify_account(existing)
        verify.return_value = profile("g-2", "mwangi@example.com", verified=True)

        body = self.client.post(GOOGLE, {"credential": "ok"}, format="json").json()

        self.assertFalse(body["created"])
        self.assertEqual(body["username"], "mwangi")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(existing.social_accounts.count(), 1)

    @patch("goldride_app.views.verify_google")
    def test_an_unverified_registration_cannot_capture_the_owner(self, verify):
        """The attack: register with a stranger's address and wait for them.

        Nothing proves the address at registration, so if a verified Google
        sign-in linked to that row the owner would be handed the attacker's
        account - password and all.
        """
        registration = self.client.post(
            "/api/auth/register/",
            {
                "username": "attacker",
                "email": "victim@example.com",
                "first_name": "Not",
                "password": "Sh1llings!2026",
            },
            format="json",
        )
        self.assertEqual(registration.status_code, 201)

        verify.return_value = profile("g-victim", "victim@example.com", verified=True)
        response = self.client.post(GOOGLE, {"credential": "ok"}, format="json")
        body = response.json()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(body["code"], "email_in_use")
        self.assertNotIn("token", body)

        # nothing was linked, and the squatted row is untouched
        self.assertEqual(SocialAccount.objects.count(), 0)
        self.assertEqual(
            User.objects.get(email="victim@example.com").username, "attacker"
        )

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
    def test_a_social_created_account_is_marked_verified(self, verify):
        """The provider proved it, so a later sign-in may link to this row."""
        verify.return_value = profile("g-6", "amina@example.com", verified=True)

        self.client.post(GOOGLE, {"credential": "ok"}, format="json")

        user = User.objects.get(email="amina@example.com")
        self.assertTrue(get_profile(user).email_verified)

    @patch("goldride_app.views.verify_linkedin")
    def test_an_unverified_provider_email_leaves_the_account_unverified(self, verify):
        verify.return_value = profile("li-7", "claimed@example.com", verified=False)

        body = self.client.post(LINKEDIN, {"code": "abc"}, format="json").json()

        user = User.objects.get(username=body["username"])
        self.assertFalse(get_profile(user).email_verified)

    @patch("goldride_app.views.verify_google")
    def test_a_refused_link_stays_refused(self, verify):
        """Retrying must not be a way through."""
        User.objects.create_user(
            "squatter", email="victim@example.com", password="Sh1llings!2026"
        )
        verify.return_value = profile("g-8", "victim@example.com", verified=True)

        for _ in range(3):
            response = self.client.post(GOOGLE, {"credential": "ok"}, format="json")
            self.assertEqual(response.status_code, 409)

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.count(), 0)

    @patch("goldride_app.views.verify_google")
    def test_an_already_linked_account_is_unaffected(self, verify):
        """Verification gates new links only - it must not lock people out."""
        user = User.objects.create_user("amina", email="amina@example.com")
        SocialAccount.objects.create(provider="google", uid="g-9", user=user)
        self.assertFalse(get_profile(user).email_verified)
        verify.return_value = profile("g-9", "amina@example.com", verified=True)

        response = self.client.post(GOOGLE, {"credential": "ok"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "amina")

    @patch("goldride_app.views.verify_google")
    def test_the_token_actually_works(self, verify):
        verify.return_value = profile("g-5", "amina@example.com", verified=True)
        token = self.client.post(GOOGLE, {"credential": "ok"}, format="json").json()["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["roles"], ["Customer"])


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.TokenAuthentication",
        ],
    }
)
class EmailLoginTests(APITestCase):
    URL = "/api/auth/login/email/"

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            "mwangi", email="Mwangi@Example.com", password="Sh1llings!2026"
        )
        Group.objects.get_or_create(name="Customer")[0].user_set.add(self.user)

    def test_correct_credentials_return_a_working_token(self):
        response = self.client.post(
            self.URL,
            {"email": "mwangi@example.com", "password": "Sh1llings!2026"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        token = response.json()["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        me = self.client.get("/api/me/").json()
        self.assertEqual(me["username"], "mwangi")
        self.assertEqual(me["roles"], ["Customer"])

    def test_email_match_is_case_insensitive(self):
        response = self.client.post(
            self.URL,
            {"email": "MWANGI@EXAMPLE.COM", "password": "Sh1llings!2026"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            self.URL, {"email": "mwangi@example.com", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_email_gives_the_same_message_as_a_wrong_password(self):
        """Otherwise the endpoint tells strangers which emails are registered."""
        unknown = self.client.post(
            self.URL, {"email": "nobody@example.com", "password": "x"}, format="json"
        )
        wrong = self.client.post(
            self.URL, {"email": "mwangi@example.com", "password": "wrong"}, format="json"
        )

        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(unknown.json(), wrong.json())

    def test_social_only_account_cannot_be_password_guessed(self):
        social = User.objects.create_user("amina", email="amina@example.com")
        social.set_unusable_password()
        social.save()

        for attempt in ["", "password", "Sh1llings!2026"]:
            response = self.client.post(
                self.URL,
                {"email": "amina@example.com", "password": attempt},
                format="json",
            )
            self.assertEqual(response.status_code, 400)

    def test_blank_email_cannot_match_a_social_user(self):
        """Social users carry email='' - an empty request must not find them."""
        ghost = User.objects.create_user("user1a2b", email="")
        ghost.set_unusable_password()
        ghost.save()

        for body in [{}, {"email": "", "password": "x"}, {"password": "x"}]:
            response = self.client.post(self.URL, body, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("token", response.json())

    def test_disabled_account_is_refused(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            self.URL,
            {"email": "mwangi@example.com", "password": "Sh1llings!2026"},
            format="json",
        )

        # authenticate() rejects inactive users, so this is indistinguishable
        # from a wrong password - which leaks less than a dedicated 403.
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("token", response.json())


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.TokenAuthentication",
        ],
    }
)
class MeTests(APITestCase):
    def setUp(self):
        cache.clear()

    def sign_in(self, user):
        from rest_framework.authtoken.models import Token

        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_social_user_without_an_email_is_flagged(self):
        user = User.objects.create_user("user1a2b", email="")
        self.sign_in(user)

        body = self.client.get("/api/me/").json()

        self.assertTrue(body["needs_email"])
        self.assertEqual(body["email"], "")

    def test_they_can_add_one(self):
        user = User.objects.create_user("user1a2b", email="")
        self.sign_in(user)

        response = self.client.patch(
            "/api/me/", {"email": "amina@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["needs_email"])
        user.refresh_from_db()
        self.assertEqual(user.email, "amina@example.com")

    def test_they_cannot_take_an_email_already_in_use(self):
        User.objects.create_user("owner", email="taken@example.com")
        user = User.objects.create_user("user1a2b", email="")
        self.sign_in(user)

        response = self.client.patch(
            "/api/me/", {"email": "taken@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.email, "")

    def test_me_reports_which_providers_are_linked(self):
        user = User.objects.create_user("amina", email="amina@example.com")
        SocialAccount.objects.create(provider="google", uid="g-1", user=user)
        self.sign_in(user)

        body = self.client.get("/api/me/").json()

        self.assertEqual(body["providers"], ["google"])
        self.assertFalse(body["has_password"])

    def test_anonymous_cannot_read_or_change_it(self):
        self.assertEqual(self.client.get("/api/me/").status_code, 401)
        self.assertEqual(
            self.client.patch("/api/me/", {"email": "x@example.com"}, format="json").status_code,
            401,
        )


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.TokenAuthentication",
        ],
    }
)
class RegistrationTests(APITestCase):
    URL = "/api/auth/register/"

    def setUp(self):
        cache.clear()

    def register(self, **overrides):
        body = {
            "email": "amina@example.com",
            "first_name": "Amina",
            "password": "Sh1llings!2026",
        }
        body.update(overrides)
        return self.client.post(self.URL, body, format="json")

    def test_a_username_is_derived_from_the_email(self):
        response = self.register()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["username"], "amina")
        self.assertTrue(User.objects.filter(username="amina").exists())

    def test_a_supplied_username_is_still_used(self):
        response = self.register(username="amina_o")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["username"], "amina_o")

    def test_a_derived_username_collision_gets_a_suffix(self):
        User.objects.create_user("amina", email="someone.else@example.com")

        response = self.register()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["username"].startswith("amina-"))

    def test_a_taken_username_is_still_rejected(self):
        User.objects.create_user("amina", email="someone.else@example.com")

        response = self.register(username="amina")

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_the_new_account_is_not_email_verified(self):
        """Nothing here proves the address, so nothing may link to it."""
        self.register()

        user = User.objects.get(email="amina@example.com")
        self.assertFalse(get_profile(user).email_verified)

    def test_the_token_it_returns_works(self):
        token = self.register().json()["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        me = self.client.get("/api/me/").json()

        self.assertEqual(me["username"], "amina")
        self.assertEqual(me["roles"], ["Customer"])


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.TokenAuthentication",
        ],
    }
)
class LogoutTests(APITestCase):
    URL = "/api/auth/logout/"

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            "mwangi", email="mwangi@example.com", password="Sh1llings!2026"
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_the_token_stops_working(self):
        self.assertEqual(self.client.get("/api/me/").status_code, 200)

        response = self.client.post(self.URL)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/me/").status_code, 401)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_signing_in_again_issues_a_fresh_token(self):
        self.client.post(self.URL)
        self.client.credentials()

        response = self.client.post(
            "/api/auth/login/email/",
            {"email": "mwangi@example.com", "password": "Sh1llings!2026"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["token"], self.token.key)

    def test_anonymous_cannot_call_it(self):
        self.client.credentials()
        self.assertEqual(self.client.post(self.URL).status_code, 401)

    def test_one_logout_does_not_touch_anybody_else(self):
        other = User.objects.create_user("amina", email="amina@example.com")
        other_token, _ = Token.objects.get_or_create(user=other)

        self.client.post(self.URL)

        self.assertTrue(Token.objects.filter(key=other_token.key).exists())


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.TokenAuthentication",
        ],
    }
)
class PurchaseRequestEmailTests(APITestCase):
    """A social sign-in with no verified address cannot be sent a checkout link."""

    URL = "/api/purchases/"

    def setUp(self):
        cache.clear()
        self.car = Car.objects.create(
            make="Toyota",
            model="Land Cruiser",
            year=2021,
            price=Decimal("8500000.00"),
            description="V8, imported.",
        )
        self.customers = Group.objects.get_or_create(name="Customer")[0]

    def sign_in(self, user):
        self.customers.user_set.add(user)
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def buy(self):
        return self.client.post(
            self.URL, {"car": self.car.pk, "phone": "0712345678"}, format="json"
        )

    def test_an_account_without_an_email_is_refused(self):
        self.sign_in(User.objects.create_user("user1a2b", email=""))

        response = self.buy()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "email_required")
        self.assertEqual(PurchaseRequest.objects.count(), 0)

    def test_adding_an_email_unblocks_it(self):
        user = User.objects.create_user("user1a2b", email="")
        self.sign_in(user)
        self.assertEqual(self.buy().status_code, 400)

        self.client.patch("/api/me/", {"email": "amina@example.com"}, format="json")

        self.assertEqual(self.buy().status_code, 201)
        self.assertEqual(PurchaseRequest.objects.count(), 1)

    def test_listing_your_own_requests_still_works_without_one(self):
        """Only the write is blocked - do not lock them out of their history."""
        self.sign_in(User.objects.create_user("user1a2b", email=""))

        self.assertEqual(self.client.get(self.URL).status_code, 200)


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
