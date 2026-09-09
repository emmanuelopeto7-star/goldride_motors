"""Refusing an address nobody can be reached at, and a password worth guessing.

Two separate jobs that both belong at the front door.

The email half exists because `EmailField` only proves an address is *shaped*
like an address. `tung6767@test.com` passes every syntax check ever written and
reaches nobody, and an account on an unreachable address is worse than no
account: it cannot verify, cannot reset a password, and cannot be told its car
arrived. Three rules, cheapest first - a name that cannot exist, a domain that
exists to be thrown away, and finally a domain that does not accept mail.

The password half is a complexity rule to sit alongside Django's own
validators, which catch short, common, numeric and name-like passwords but
would accept "aaaaaaaaaaaa".
"""

import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger("goldride")


# Domains reserved by RFC 2606 and RFC 6761 for documentation and testing.
# They are guaranteed never to resolve, so mail to them is guaranteed to fail.
RESERVED_DOMAINS = frozenset({
    "example.com", "example.net", "example.org",
    "test.com",
})

# The TLDs from the same RFCs. Anything under them is equally unreachable.
RESERVED_TLDS = frozenset({"test", "example", "invalid", "localhost", "local"})

# Throwaway inbox providers. Not exhaustive - no such list is - and it does not
# need to be: this is here to stop the lazy signup, not to win an arms race
# against somebody determined to have a disposable address. The MX check below
# is the rule that generalises.
DISPOSABLE_DOMAINS = frozenset({
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "sharklasers.com",
    "10minutemail.com", "10minutemail.net", "tempmail.com", "temp-mail.org",
    "throwawaymail.com", "yopmail.com", "yopmail.fr", "getnada.com",
    "trashmail.com", "trashmail.de", "dispostable.com", "maildrop.cc",
    "fakeinbox.com", "mailnesia.com", "mytemp.email", "spamgourmet.com",
    "mohmal.com", "emailondeck.com", "burnermail.io", "moakt.com",
    "tempr.email", "discard.email", "mailcatch.com", "inboxkitten.com",
    "spam4.me", "grr.la", "tempmailo.com", "minuteinbox.com",
})


def _setting(name, default):
    return getattr(settings, name, default)


class _Policy:
    """Settings read lazily, so `override_settings` works in tests."""

    @property
    def extra_blocked(self):
        raw = _setting("EMAIL_BLOCKED_DOMAINS", "")
        return frozenset(
            d.strip().lower().lstrip("@") for d in raw.split(",") if d.strip()
        )

    @property
    def reject_reserved(self):
        return _setting("EMAIL_REJECT_RESERVED_DOMAINS", True)

    @property
    def reject_disposable(self):
        return _setting("EMAIL_REJECT_DISPOSABLE_DOMAINS", True)

    @property
    def require_deliverable(self):
        return _setting("EMAIL_REQUIRE_DELIVERABLE_DOMAIN", True)


policy = _Policy()

# One message for every rejection. Telling somebody *which* rule caught them is
# a free lesson in how to get around it, and "that address will not reach you"
# is the true statement in all three cases.
REJECTION = (
    "Enter an email address that can receive mail. Disposable and test "
    "addresses are not accepted."
)


def _domain_of(value):
    return (value or "").strip().rsplit("@", 1)[-1].lower().rstrip(".")


def domain_accepts_mail(domain):
    """True if this domain publishes somewhere to deliver mail.

    Fails *open* on a timeout or a broken resolver: a DNS wobble on our side
    must not stop the world from signing up. It fails *closed* only when the
    answer is definite - the domain does not exist, or it exists and publishes
    no route for mail at all.
    """
    try:
        import dns.exception
        import dns.resolver
    except ImportError:
        # The dependency is optional on purpose: without it the two rules above
        # still apply, and signup keeps working rather than 500ing.
        logger.warning("dnspython not installed - skipping MX check for %s", domain)
        return True

    resolver = dns.resolver.Resolver()
    resolver.lifetime = _setting("EMAIL_DNS_TIMEOUT", 5)
    resolver.timeout = resolver.lifetime

    try:
        answers = resolver.resolve(domain, "MX")
        # A null MX (RFC 7505) is a domain stating outright that it takes no
        # mail. Exchange "." is the whole signal.
        if any(str(rdata.exchange).rstrip(".") == "" for rdata in answers):
            return False
        return len(answers) > 0
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        # No MX record is not the same as no mail: RFC 5321 says fall back to
        # the address record. Plenty of small domains rely on exactly that.
        for record in ("A", "AAAA"):
            try:
                if len(resolver.resolve(domain, record)) > 0:
                    return True
            except Exception:
                continue
        return False
    except (dns.exception.Timeout, dns.resolver.NoNameservers):
        logger.warning("DNS did not answer for %s - allowing the address", domain)
        return True
    except Exception:
        logger.exception("MX lookup failed for %s - allowing the address", domain)
        return True


def validate_deliverable_email(value):
    """Raise ValidationError if this address cannot plausibly receive mail."""
    domain = _domain_of(value)
    if not domain:
        raise ValidationError(REJECTION)

    tld = domain.rsplit(".", 1)[-1] if "." in domain else domain

    if policy.reject_reserved and (
        domain in RESERVED_DOMAINS or tld in RESERVED_TLDS
    ):
        raise ValidationError(REJECTION)

    if policy.reject_disposable and (
        domain in DISPOSABLE_DOMAINS or domain in policy.extra_blocked
    ):
        raise ValidationError(REJECTION)

    if policy.require_deliverable and not domain_accepts_mail(domain):
        raise ValidationError(REJECTION)

    return value


# --- passwords -------------------------------------------------------------

CLASSES = (
    ("a lower-case letter", re.compile(r"[a-z]")),
    ("an upper-case letter", re.compile(r"[A-Z]")),
    ("a number", re.compile(r"[0-9]")),
    ("a symbol", re.compile(r"[^A-Za-z0-9]")),
)


class ComplexityValidator:
    """Require a mix of character types - unless the password is long enough.

    Django's own validators reject short, common, numeric and name-like
    passwords, which leaves "aaaaaaaaaaaa" and "kenyakenyakenya" perfectly
    acceptable. This asks for `required` of the four character classes.

    Three of four rather than all four: forcing every class is what produces
    "Password1!" on every account in the country.

    And `passphrase_length` characters buys exemption from the rule entirely,
    because at that length the mix has stopped mattering.
    "a-long-enough-passphrase" is twenty-four characters and two classes;
    "Passw0rd!" is nine and four, and is the weaker of the two by a wide
    margin. Composition rules push people towards the second - which is why
    NIST stopped recommending them - so length is allowed to answer instead.
    """

    def __init__(self, required=3, passphrase_length=16):
        self.required = required
        self.passphrase_length = passphrase_length

    def validate(self, password, user=None):
        password = password or ""

        # Long enough to stand on its own. RepetitionValidator still applies,
        # so this is not a way to smuggle "aaaaaaaaaaaaaaaaaa" through.
        if len(password) >= self.passphrase_length:
            return

        present = [name for name, pattern in CLASSES if pattern.search(password)]
        if len(present) < self.required:
            missing = [name for name, _ in CLASSES if name not in present]
            raise ValidationError(
                f"Use a stronger mix: at least {self.required} of a lower-case "
                f"letter, an upper-case letter, a number and a symbol - or "
                f"simply make it {self.passphrase_length} characters or longer. "
                f"Yours is missing {', '.join(missing)}.",
                code="password_not_complex",
            )

    def get_help_text(self):
        return (
            f"Your password must combine at least {self.required} of: a "
            "lower-case letter, an upper-case letter, a number, a symbol - "
            f"or be at least {self.passphrase_length} characters long."
        )


class RepetitionValidator:
    """Reject a password that is one character or one short run repeated.

    "aaaaaaaaaaaa" and "abcabcabcabc" both clear a length rule and a
    complexity rule while carrying almost no entropy.
    """

    def __init__(self, max_run=4):
        self.max_run = max_run

    def validate(self, password, user=None):
        password = password or ""

        if re.search(r"(.)\1{%d,}" % (self.max_run - 1), password):
            raise ValidationError(
                f"Do not repeat the same character {self.max_run} or more "
                "times in a row.",
                code="password_repetitive",
            )

        # A password built by repeating a short unit: the whole string is that
        # unit over and over, and there are at least three of them.
        for size in range(1, len(password) // 3 + 1):
            unit = password[:size]
            if unit * (len(password) // size) == password and len(password) // size >= 3:
                raise ValidationError(
                    "Do not build a password by repeating a short sequence.",
                    code="password_repetitive",
                )

    def get_help_text(self):
        return (
            f"Your password cannot repeat one character {self.max_run}+ times "
            "in a row, or repeat a short sequence."
        )
