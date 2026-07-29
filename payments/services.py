import requests
from django.conf import settings
from decouple import config

PAYSTACK_URL = config('PAYSTACK_URL')


def start_paystack_payment(payment, email):
    resp = requests.post(
        PAYSTACK_URL,
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        json={
            "email": email,
            "amount": int(payment.amount * 100),
            "currency": "KES",
            "reference": str(payment.reference),
        },
        timeout=15,
    )

    try:
        data = resp.json()
    except ValueError:
        return None

    if not data.get("status"):
        return None

    return data.get("data", {}).get("authorization_url")