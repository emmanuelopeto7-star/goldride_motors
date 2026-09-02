import base64
import requests
from datetime import datetime
from decimal import ROUND_CEILING
from decouple import config

MPESA_ENVIRONMENT = config("MPESA_ENVIRONMENT", default="sandbox")
MPESA_CONSUMER_KEY = config("MPESA_CONSUMER_KEY")
MPESA_CONSUMER_SECRET = config("MPESA_CONSUMER_SECRET")
MPESA_SHORTCODE = config("MPESA_SHORTCODE")
MPESA_PASSKEY = config("MPESA_PASSKEY")
MPESA_CALLBACK_URL = config("MPESA_CALLBACK_URL")

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


def start_mpesa_payment(payment, phone):
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
