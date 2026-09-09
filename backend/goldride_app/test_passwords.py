"""Password reset, password strength, and who is allowed to sign up.

The email rules are switched on explicitly here with override_settings: the
test run turns the reserved-domain rule off so the suite's ~155 example.com
fixtures keep working, so anything asserting that rule has to ask for it.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .passwords import make_token, read_token, ResetError
from .validators import ComplexityValidator, RepetitionValidator

User = get_user_model()

STRONG = "Sh1llings!2026"
ALSO_STRONG = "N4irobi#Matatu"

RESET = "/api/auth/password/reset/"
CONFIRM = "/api/auth/password/reset/confirm/"
CHANGE = "/api/auth/password/change/"

class ThrottleFreeTestCase(TestCase):
    """Reset the throttle between tests.

    DRF keeps its rate-limit history in the default cache, which outlives an
    individual test - so a class that signs up eight times exhausts the 10/hour
    register scope partway through and the later assertions see 429 instead of
    the 400 they are checking for. Clearing the cache per test keeps each one
    measuring what it means to, while leaving the limits themselves in force.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()


class PasswordResetFlowTests(ThrottleFreeTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="wanjiku", email="wanjiku@gmail.com", password=STRONG
        )
        mail.outbox = []

    def test_request_sends_a_link(self):
        response = self.client.post(RESET, {"email": "wanjiku@gmail.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset-password/", mail.outbox[0].body)

    def test_unknown_address_answers_identically_and_sends_nothing(self):
        """The response must not reveal whether an account exists."""
        hit = self.client.post(RESET, {"email": "wanjiku@gmail.com"}, format="json")
        mail.outbox = []
        miss = self.client.post(RESET, {"email": "nobody@gmail.com"}, format="json")

        self.assertEqual(hit.status_code, miss.status_code)
        self.assertEqual(hit.json(), miss.json())
        self.assertEqual(len(mail.outbox), 0)

    def test_social_only_account_gets_no_link(self):
        """An unusable password must not be quietly turned into a usable one."""
        social = User.objects.create_user(username="g", email="g@gmail.com")
        social.set_unusable_password()
        social.save()
        mail.outbox = []

        response = self.client.post(RESET, {"email": "g@gmail.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_link_sets_the_new_password(self):
        token = make_token(self.user)
        response = self.client.post(
            CONFIRM, {"token": token, "password": ALSO_STRONG}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(ALSO_STRONG))
        self.assertFalse(self.user.check_password(STRONG))

    def test_link_works_only_once(self):
        token = make_token(self.user)
        first = self.client.post(
            CONFIRM, {"token": token, "password": ALSO_STRONG}, format="json"
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            CONFIRM, {"token": token, "password": "Th1rdPassword!"}, format="json"
        )
        self.assertEqual(second.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(ALSO_STRONG))

    def test_reset_revokes_every_existing_token(self):
        """Whoever took the account must not keep it after the owner resets."""
        stolen = Token.objects.create(user=self.user).key
        self.client.post(
            CONFIRM, {"token": make_token(self.user), "password": ALSO_STRONG},
            format="json",
        )
        self.assertFalse(Token.objects.filter(key=stolen).exists())

    def test_tampered_and_foreign_tokens_are_refused(self):
        for bad in ["nonsense", make_token(self.user) + "x"]:
            response = self.client.post(
                CONFIRM, {"token": bad, "password": ALSO_STRONG}, format="json"
            )
            self.assertEqual(response.status_code, 400)

    def test_token_dies_when_the_address_changes(self):
        token = make_token(self.user)
        self.user.email = "elsewhere@gmail.com"
        self.user.save()

        with self.assertRaises(ResetError):
            read_token(token)

    def test_expired_token_is_refused(self):
        token = make_token(self.user)
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            with self.assertRaises(ResetError):
                read_token(token)

    def test_weak_password_is_refused_at_confirm(self):
        response = self.client.post(
            CONFIRM, {"token": make_token(self.user), "password": "password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())


class PasswordChangeTests(ThrottleFreeTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="otieno", email="otieno@gmail.com", password=STRONG
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_change_requires_the_current_password(self):
        response = self.client.post(
            CHANGE, {"current_password": "wrong", "password": ALSO_STRONG},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG))

    def test_change_succeeds_and_returns_a_working_token(self):
        response = self.client.post(
            CHANGE, {"current_password": STRONG, "password": ALSO_STRONG},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(ALSO_STRONG))

        # The old token is gone; the returned one works.
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())
        fresh = APIClient()
        fresh.credentials(HTTP_AUTHORIZATION=f"Token {response.json()['token']}")
        self.assertEqual(fresh.get("/api/me/").status_code, 200)

    def test_anonymous_cannot_change_a_password(self):
        response = APIClient().post(
            CHANGE, {"current_password": STRONG, "password": ALSO_STRONG},
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_cannot_reuse_the_same_password(self):
        response = self.client.post(
            CHANGE, {"current_password": STRONG, "password": STRONG}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class PasswordStrengthTests(ThrottleFreeTestCase):
    """The policy as it is actually enforced at the registration door."""

    URL = "/api/auth/register/"

    def signup(self, password):
        return self.client.post(
            self.URL,
            {
                "email": "newcomer@gmail.com",
                "first_name": "New",
                "password": password,
            },
            format="json",
        )

    def test_strong_password_is_accepted(self):
        self.assertEqual(self.signup(STRONG).status_code, 201)

    def test_rejects(self):
        cases = {
            "short": "Sh1ll!ng",              # 8 chars, under the 12 minimum
            "common": "password123456",        # on Django's common list
            "all numeric": "859372048163",
            "no mix": "shillingsmoney",        # one character class only
            "one char repeated": "aaaaaaaaaaaaaa",
            "repeated unit": "Ab1!Ab1!Ab1!",
        }
        for label, password in cases.items():
            with self.subTest(label):
                response = self.signup(password)
                self.assertEqual(response.status_code, 400, f"{label} was accepted")
                self.assertIn("password", response.json())

    def test_password_cannot_be_the_email(self):
        response = self.client.post(
            self.URL,
            {"email": "newcomer@gmail.com", "first_name": "New",
             "password": "newcomer@gmail.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class ValidatorUnitTests(TestCase):
    def test_complexity_counts_three_of_four(self):
        validator = ComplexityValidator(required=3, passphrase_length=16)
        validator.validate("Shillings1")            # lower + upper + digit
        validator.validate("shillings1!")           # lower + digit + symbol
        with self.assertRaises(Exception):
            validator.validate("shillingsmoney")    # lower only, 14 chars

    def test_length_excuses_the_mix(self):
        """A long passphrase is strong without a symbol bolted onto it."""
        validator = ComplexityValidator(required=3, passphrase_length=16)
        validator.validate("a-long-enough-passphrase")
        validator.validate("correct horse battery staple")

    def test_length_does_not_excuse_repetition(self):
        with self.assertRaises(Exception):
            RepetitionValidator(max_run=4).validate("aaaaaaaaaaaaaaaaaaaa")

    def test_repetition(self):
        validator = RepetitionValidator(max_run=4)
        validator.validate("Sh1llings!2026")
        with self.assertRaises(Exception):
            validator.validate("Shaaaallings1!")
        with self.assertRaises(Exception):
            validator.validate("Ab1!Ab1!Ab1!")


@override_settings(
    EMAIL_REJECT_RESERVED_DOMAINS=True,
    EMAIL_REJECT_DISPOSABLE_DOMAINS=True,
    EMAIL_REQUIRE_DELIVERABLE_DOMAIN=False,
)
class SignupEmailTests(ThrottleFreeTestCase):
    """The reserved and disposable rules. The DNS rule is covered separately
    because it must not make a network call."""

    URL = "/api/auth/register/"

    def signup(self, email):
        return self.client.post(
            self.URL,
            {"email": email, "first_name": "New", "password": STRONG},
            format="json",
        )

    def test_rejects_unreachable_domains(self):
        cases = [
            "tung6767@test.com",        # the address that prompted this
            "someone@example.com",
            "someone@example.org",
            "someone@goldride.test",
            "someone@whatever.invalid",
            "someone@mailinator.com",
            "someone@10minutemail.com",
            "someone@yopmail.com",
            # Same services on other domains. These slipped through the
            # hand-written list and are why the maintained one is wired in.
            "someone@mailinator.net",
            "someone@temp-mail.io",
            "someone@1secmail.com",
            "someone@emailfake.com",
        ]
        for email in cases:
            with self.subTest(email):
                # Per iteration, not per test: this list is longer than the
                # 10/hour register throttle, so without it the tail of the
                # loop measures rate limiting instead of the email rule.
                cache.clear()
                response = self.signup(email)
                self.assertEqual(response.status_code, 400, f"{email} was accepted")
                self.assertIn("email", response.json())

    def test_accepts_a_real_address(self):
        self.assertEqual(self.signup("wanjiku@gmail.com").status_code, 201)

    def test_the_maintained_list_is_actually_loaded(self):
        """A silent ImportError here would quietly drop ~8,700 domains."""
        from .validators import MAINTAINED_DISPOSABLE

        self.assertGreater(len(MAINTAINED_DISPOSABLE), 5000)

    def test_case_and_padding_do_not_evade_the_rule(self):
        for email in ["Someone@Example.COM", "someone@TEST.com"]:
            with self.subTest(email):
                self.assertEqual(self.signup(email).status_code, 400)

    @override_settings(EMAIL_BLOCKED_DOMAINS="banned.co.ke,other.com")
    def test_extra_blocklist_from_settings(self):
        self.assertEqual(self.signup("someone@banned.co.ke").status_code, 400)

    def test_changing_your_address_obeys_the_same_rule(self):
        user = User.objects.create_user(
            username="w", email="wanjiku@gmail.com", password=STRONG
        )
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}"
        )
        response = client.patch(
            "/api/me/", {"email": "tung6767@test.com"}, format="json"
        )
        self.assertEqual(response.status_code, 400)


@override_settings(
    EMAIL_REJECT_RESERVED_DOMAINS=False,
    EMAIL_REJECT_DISPOSABLE_DOMAINS=False,
    EMAIL_REQUIRE_DELIVERABLE_DOMAIN=True,
)
class DeliverabilityTests(ThrottleFreeTestCase):
    """The MX rule, with DNS mocked - no test may need a resolver."""

    URL = "/api/auth/register/"

    def signup(self, email="someone@nosuchdomain-xyz.com"):
        return self.client.post(
            self.URL,
            {"email": email, "first_name": "New", "password": STRONG},
            format="json",
        )

    @patch("goldride_app.validators.domain_accepts_mail", return_value=False)
    def test_domain_with_no_mail_route_is_refused(self, _):
        response = self.signup()
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    @patch("goldride_app.validators.domain_accepts_mail", return_value=True)
    def test_domain_that_accepts_mail_is_allowed(self, _):
        self.assertEqual(self.signup().status_code, 201)

    def test_dns_failure_fails_open(self):
        """A resolver outage must not stop the world signing up."""
        import dns.exception

        from .validators import domain_accepts_mail

        with patch("dns.resolver.Resolver.resolve", side_effect=dns.exception.Timeout):
            self.assertTrue(domain_accepts_mail("gmail.com"))

    def test_nonexistent_domain_fails_closed(self):
        import dns.resolver

        from .validators import domain_accepts_mail

        with patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
            self.assertFalse(domain_accepts_mail("nosuchdomain-xyz-9911.com"))


@override_settings(REST_FRAMEWORK={
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_RATES": {"login": "5/hour"},
})
class LoginThrottleTests(ThrottleFreeTestCase):
    """Five wrong passwords an hour, on both sign-in doors.

    `/api/auth/login/` was DRF's `obtain_auth_token`, which sets
    `throttle_classes = ()` and so accepted unlimited guesses. The email door
    next to it was already limited, which made the limit decorative - anybody
    stopped there could move one URL across.
    """

    BY_USERNAME = "/api/auth/login/"
    BY_EMAIL = "/api/auth/login/email/"

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="wanjiku", email="wanjiku@gmail.com", password=STRONG
        )

    def guess_by_username(self):
        return self.client.post(
            self.BY_USERNAME, {"username": "wanjiku", "password": "wrong"},
            format="json",
        )

    def guess_by_email(self):
        return self.client.post(
            self.BY_EMAIL, {"email": "wanjiku@gmail.com", "password": "wrong"},
            format="json",
        )

    def test_the_username_door_stops_after_five(self):
        for attempt in range(5):
            self.assertEqual(self.guess_by_username().status_code, 400, f"attempt {attempt + 1}")
        self.assertEqual(self.guess_by_username().status_code, 429)

    def test_the_email_door_stops_after_five(self):
        for attempt in range(5):
            self.assertEqual(self.guess_by_email().status_code, 400, f"attempt {attempt + 1}")
        self.assertEqual(self.guess_by_email().status_code, 429)

    def test_the_two_doors_share_one_budget(self):
        """The whole point: exhausting one must not leave the other open."""
        for _ in range(5):
            self.guess_by_username()

        self.assertEqual(self.guess_by_email().status_code, 429)

    def test_a_correct_password_still_works_within_the_limit(self):
        self.guess_by_username()
        response = self.client.post(
            self.BY_USERNAME, {"username": "wanjiku", "password": STRONG},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("token"))
