import requests
from django.conf import settings
from decouple import config
import hmac
import hashlib
import uuid

PAYSTACK_BASE_URL = config('PAYSTACK_BASE_URL')


def start_paystack_payment(payment, email):
    url, _ = start_paystack_payment_detailed(payment, email)
    return url


def start_paystack_payment_detailed(payment, email):
    paystack_ref = str(uuid.uuid4())

    resp = requests.post(
        f"{PAYSTACK_BASE_URL}/transaction/initialize",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        json={
            "email": email,
            "amount": int(payment.amount * 100),
            "currency": "KES",
            "reference": paystack_ref,
        },
        timeout=30,
    )

    try:
        data = resp.json()
    except ValueError:
        return None, f"Paystack returned HTTP {resp.status_code}"

    if not data.get("status"):
        return None, data.get("message") or "Paystack rejected the request"

    payment.paystack_ref = paystack_ref
    payment.save()

    return data.get("data", {}).get("authorization_url"), "ok"


def verify_paystack_signature(raw_body, signature):
    if not signature:
        return False

    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def verify_paystack_payment(reference):
    resp = requests.get(
        f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        # 120s was long enough for one slow verify to hold a webhook, a
        # sweep or a customer's page load open for two minutes.
        timeout=20,
    )

    try:
        data = resp.json()
    except ValueError:
        return None

    if not data.get("status"):
        return None

    return data.get("data")
