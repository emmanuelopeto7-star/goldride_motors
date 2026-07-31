# Goldride Motors — Backend

A Django REST API for a Kenyan car dealership that **imports vehicles to order**.

Customers browse stock, enquire about a car, follow their import from Japan or Dubai to
delivery, and pay deposits by card or M-PESA.

---

## What it does

**Car catalogue** — public listings with photo galleries, filtering, search and sorting.
Staff add cars through the admin; there is no public write endpoint.

**Enquiries** — a customer asks about a car and staff get an email alert. The endpoint
only accepts submissions; reading the list needs a staff login.

**Import tracking** — each order gets a private link with a random ID. The customer sees
where their car is (ordered → shipped → at port → clearing → delivered) and nothing else:
no names, no phone numbers, no amounts.

**Payments** — card via Paystack, mobile money via M-PESA, or bank transfer recorded by
hand. Every payment is confirmed with the provider before it is marked paid, and a
reconciliation command catches payments whose notification went missing.

**Balances** — each import order has a total; amount paid and balance are calculated from
the payments, so they can never be out of date.

---

## Setting it up

### You will need

- Python 3.14
- Git
- PostgreSQL (optional — it falls back to SQLite)
- A Paystack account for card payments (test keys are free)
- A Daraja account at [developer.safaricom.co.ke](https://developer.safaricom.co.ke) for
  M-PESA — **sign up early, approval can take days**

### 1. Get the code

```bash
git clone <repository-url>
cd goldride_motors
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
.\venv\Scripts\Activate.ps1
```

On Windows, if PowerShell blocks the script:

```bash
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

On Mac or Linux use `source venv/bin/activate`.

Your prompt should now start with `(venv)`.

### 3. Install the dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Create the `.env` file

Make a file called `.env` in the project root and paste this in, replacing the
placeholders:

```
SECRET_KEY = paste-a-generated-key-here
DEBUG = True
ALLOWED_HOSTS = localhost,127.0.0.1

PAYSTACK_SECRET_KEY = sk_test_your_key_here
PAYSTACK_BASE_URL = https://api.paystack.co

MPESA_ENVIRONMENT = sandbox
MPESA_CONSUMER_KEY = your_daraja_consumer_key
MPESA_CONSUMER_SECRET = your_daraja_consumer_secret
MPESA_SHORTCODE = 174379
MPESA_PASSKEY = your_64_character_passkey
MPESA_CALLBACK_URL = https://example.com/api/payments/mpesa/callback/
```

Generate a secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**`.env` is gitignored and must never be committed.**

Two things people get wrong:

- **`PAYSTACK_BASE_URL` is the host only** — no path on the end. The code builds the rest.
- **`MPESA_PASSKEY` is not the Password field.** Daraja's simulator shows a pre-built
  `Password`; you want the field labelled **Passkey**, 64 hex characters.

### 5. Choose a database

If you do nothing, the project uses a local SQLite file and works immediately. Good
enough to explore.

For PostgreSQL, set `DATABASE_URL` as an environment variable:

```bash
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/goldride"
```

Create the database first:

```sql
CREATE DATABASE goldride;
CREATE USER goldride_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE goldride TO goldride_user;
```

### 6. Set up the database tables

```bash
python manage.py migrate
```

### 7. Create your admin account

```bash
python manage.py createsuperuser
```

### 8. Create the staff roles

```bash
python manage.py setup_roles
```

### 9. Run it

```bash
python manage.py runserver
```

- API — `http://127.0.0.1:8000/api/cars/`
- Admin — `http://127.0.0.1:8000/admin/`

Add a car in the admin and reload the API to see it.

---

## Using it

### The admin

`http://127.0.0.1:8000/admin/` is where staff work.

- **Cars** — add cars and photos
- **Inquiries** — read what customers have sent
- **Import orders** — customer details, shipment stage, total price. Milestones and
  payments appear on the same page.
- **Payments** — raise an invoice: choose the order, set the amount and method, leave the
  status `pending`. The reference appears after saving — that's what the customer needs.

### The API

| Method | Path | Who |
|---|---|---|
| `GET` | `/api/cars/` | anyone |
| `GET` | `/api/cars/<id>/` | anyone |
| `POST` | `/api/inquiries/` | anyone |
| `GET` | `/api/track/<token>/` | anyone with the link |
| `POST` | `/api/payments/initiate/` | anyone with a reference |
| `POST` | `/api/auth/login/` | staff |
| `GET` | `/api/inquiries/all/` | staff token |

Filtering examples:

```
/api/cars/?make=Toyota
/api/cars/?search=probox
/api/cars/?ordering=-price
```

### Commands

```bash
python manage.py payments              # list every payment
python manage.py card_pay <ref> <email>    # create a Paystack checkout link
python manage.py mpesa_pay <ref> <phone>   # send a payment prompt to a phone
python manage.py reconcile_payments    # sync stuck payments with the provider
python manage.py setup_roles           # create the Sales/Manager/Customer groups
```

---

## Taking a test payment

### Card

1. Admin → Payments → Add. Amount `500`, method `card`, status `pending`. Save.
2. `python manage.py payments` and copy the reference.
3. `python manage.py card_pay <reference> test@example.com`
4. Open the link it prints and pay with the sandbox card:

```
Card    4084 0840 8408 4081
CVV     408
Expiry  any future date
PIN     0000
OTP     123456
```

5. `python manage.py payments` — it should say `paid`.

That card has a low limit, so test with a few thousand shillings rather than millions.

For Paystack to notify you automatically, set your public URL in the Paystack dashboard
under **Settings → API Keys & Webhooks**.

### M-PESA

Safaricom has to be able to reach your computer, so you need a tunnel:

1. `cloudflared tunnel --url http://localhost:8000`
2. Copy the `https://....trycloudflare.com` address it prints.
3. Put it in `.env` as `MPESA_CALLBACK_URL`, with
   `/api/payments/mpesa/callback/` on the end.
4. **Restart `runserver`** — `.env` is only read at startup.
5. Admin → Payments → Add, method `mpesa`, status `pending`.
6. `python manage.py mpesa_pay <reference> 254712345678`
7. Answer the prompt on the phone within about 60 seconds.

The sandbox number `254708374149` has no real phone behind it and always times out. Use a
real Safaricom number.

**If a payment gets stuck on `pending`, run `python manage.py reconcile_payments`.** It
asks the provider what actually happened. Notifications do get lost, and this is how you
catch it.

---

## Staff roles

`python manage.py setup_roles` creates three groups:

| | Sales | Manager | Customer |
|---|---|---|---|
| Cars, inquiries, orders | view, add, change | + delete | — |
| Payments | view only | view, add, change | — |

Nobody can delete a payment. Sales cannot create one, because creating a payment means
setting an amount a customer will be asked to pay.

To add a staff member: Admin → Users → Add user, tick **Staff status**, leave
**Superuser** off, and assign a group.

---

## Known limitations

- **No automated tests.** Everything has been checked by hand.
- **No customer accounts yet** — customers hold a tracking link and a payment reference.
  The groundwork is in place but the endpoints are not built.
- **Uploaded images are stored on local disk** and will be lost on a hosting platform that
  resets its filesystem.
- **Email only prints to the terminal**; nothing is actually delivered.
- **Development settings.** `DEBUG` is on. Do not put this online without changing it.
- If a customer opens two checkout links and pays the older one, it will not be matched
  automatically.

---

## Common problems

**`Unknown command`** — a management command file is missing, or an `__init__.py` is
absent from `management/` or `management/commands/`.

**`is not a valid UUID`** — you used a shortened reference. Copy all 36 characters.

**`DisallowedHost`** — add the host to `ALLOWED_HOSTS` and restart.

**No M-PESA callback arrives** — the tunnel is down, the callback URL is stale, or
`runserver` was not restarted after editing `.env`.

**Admin has no styling after turning `DEBUG` off** — run
`python manage.py collectstatic`.

**On Windows**, `curl` and `grep` do not behave like the tutorials. Use `Select-String`
instead of `grep`, and prefer the management commands above.
