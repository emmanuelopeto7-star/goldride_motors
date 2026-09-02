import base64
import logging
import requests
from datetime import datetime
from decimal import ROUND_CEILING
from decouple import config

logger = logging.getLogger("goldride.payments")

# Defaulted to empty rather than required, and checked at the point of use
# instead. These are read when the module is imported, and the import chain
# runs from django.contrib.admin's autodiscover - so a single missing M-PESA
# value took the entire site down at boot, admin and storefront included, over
# one payment method. A misconfigured integration should break that
# integration.
MPESA_ENVIRONMENT = config("MPESA_ENVIRONMENT", default="sandbox")
MPESA_CONSUMER_KEY = config("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = config("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = config("MPESA_SHORTCODE", default="")
MPESA_PASSKEY = config("MPESA_PASSKEY", default="")
MPESA_CALLBACK_URL = config("MPESA_CALLBACK_URL", default="")

if MPESA_ENVIRONMENT == "production":
    MPESA_BASE_URL = "https://api.safaricom.co.ke"
else:
    MPESA_BASE_URL = "https://sandbox.safaricom.co.ke"


def get_mpesa_token():
    try:
        resp = requests.get(
            f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
            auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET),
            timeout=10,
        )
        data = resp.json()
    except ValueError:
        return None

    return data.get("access_token")


def build_password():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}".encode()
    ).decode()
    return password, timestamp


def whole_shillings(amount):
    """What Daraja can actually move, rounded up.

    The STK push takes an integer - M-PESA does not deal in cents - and this
    used to be a bare int(), which truncates. An invoice of 5,000.75 asked the
    customer for 5,000 and was then marked paid in full, because the callback
    re-queries the status and never compares the amount: 75 cents quietly
    uncollected on an order that reads as settled.

    Rounded up rather than to nearest, because the two errors are not equal.
    Over by less than a shilling is noise; under by any amount is a balance
    that can never be cleared through this rail.
    """
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def missing_settings():
    """Which M-PESA settings have no value, for a message worth reading."""
    return [
        name
        for name, value in (
            ("MPESA_CONSUMER_KEY", MPESA_CONSUMER_KEY),
            ("MPESA_CONSUMER_SECRET", MPESA_CONSUMER_SECRET),
            ("MPESA_SHORTCODE", MPESA_SHORTCODE),
            ("MPESA_PASSKEY", MPESA_PASSKEY),
            ("MPESA_CALLBACK_URL", MPESA_CALLBACK_URL),
        )
        if not value
    ]


def start_mpesa_payment(payment, phone):
    absent = missing_settings()
    if absent:
        # Returning None is what the caller already does with a Safaricom
        # outage, so this needs no new handling upstream - but it would be
        # invisible without the log.
        logger.error(
            "M-PESA is not configured: %s. Payment %s was not sent.",
            ", ".join(absent),
            payment.reference,
        )
        return None

    token = get_mpesa_token()
    if token is None:
        return None

    password, timestamp = build_password()

    resp = requests.post(
        f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": whole_shillings(payment.amount),
            "PartyA": phone,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": MPESA_CALLBACK_URL,
            "AccountReference": "GOLDRIDE",
            "TransactionDesc": "Car payment",
        },
        timeout=30,
    )

    try:
        data = resp.json()
    except ValueError:
        return None

    checkout_id = data.get("CheckoutRequestID")
    if checkout_id:
        payment.checkout_request_id = checkout_id
        payment.save()

    return data


def query_mpesa_payment(checkout_request_id):
    token = get_mpesa_token()
    if token is None:
        return None

    password, timestamp = build_password()

    resp = requests.post(
        f"{MPESA_BASE_URL}/mpesa/stkpushquery/v1/query",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        },
        timeout=30,
    )

    try:
        return resp.json()
    except ValueError:
        return None
