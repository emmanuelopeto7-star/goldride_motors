# Goldride Motors — Backend

A Django REST API for a Kenyan luxury car dealership that **imports vehicles to order**.
Customers browse stock, enquire about a car, follow their import from Japan or Dubai to
delivery, and pay deposits by card or M-PESA.

Replaces the previous Laravel site at goldridemotors.co.ke.

The business model shapes the design: money changes hands **weeks before a car arrives**,
so the system's real job is being certain about payments and shipments — not running a
shopfront.

---

## Contents

- [Features](#features)
- [Stack](#stack)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [The admin](#the-admin)
- [Management commands](#management-commands)
- [Taking payments](#taking-payments)
- [Staff roles](#staff-roles)
- [Security decisions](#security-decisions)
- [Testing](#testing)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)

---

## Features

### Car catalogue
Public, read-only listings with photo galleries. Filter by make, model, year, condition
(new/used) and availability (available/reserved/sold); search descriptions; sort by price
or year; 12 per page. Staff add cars through the admin — there is no public write endpoint.

### Customer enquiries
A customer asks about a specific car and staff get an email alert immediately. The endpoint
**only accepts submissions** — reading the list requires a staff token, because a public
list would expose every customer's name and phone number. Rate-limited to 5/hour.

### Import tracking
Each import order gets a UUID token. The customer follows their car through five stages —
ordered, shipped, at port, clearing, delivered — with a note on each milestone. The
tracking page exposes only the car description, the current stage and the milestone
history. Rate-limited to 20/hour.

### Payments
Two collection rails against one invoice:

- **Card** via Paystack — a hosted checkout page (Stripe does not operate in Kenya)
- **M-PESA** via Safaricom Daraja — an STK push that prompts the customer's phone for a PIN
- **Manual** — bank transfers, recorded by staff

Payments are verified against the provider before anything is marked paid, and a
reconciliation command catches payments whose notification was lost.

### Order balances
An import order stores a total; `amount_paid`, `balance` and `is_settled` are computed
live from paid payments, so they cannot drift out of sync.

---

## Stack

| | |
|---|---|
| Python | 3.14 |
| Django | 6.0 |
| API | Django REST Framework 3.17 |
| Database | PostgreSQL (via psycopg 3) |
| Config | python-decouple (`.env`) |
| Filtering | django-filter |
| Cards | Paystack |
| Mobile money | M-PESA Daraja |
| Images | Pillow, stored on local disk |

**Installed but deliberately not wired up:** celery, redis, cloudinary, django-money,
django-axes, django-cors-headers, drf-spectacular. They are in `requirements.txt` from
early planning; none are in `INSTALLED_APPS`. Do not assume they are active.

---

## Project structure

```
goldride_motors/
├── goldride_project/        settings, root urls, wsgi/asgi
├── cars/                    Car, CarImage — public read-only API
├── inquiries/               Inquiry — public write-only API
├── imports/                 ImportOrder, ImportMilestone — token tracking
├── payments/                Payment, Paystack + M-PESA integration
│   ├── services.py          Paystack: initialize, verify, signature check
│   ├── mpesa.py             Daraja: token, STK push, status query
│   └── management/commands/ payments, card_pay, mpesa_pay, reconcile_payments
├── goldride_app/            holds the setup_roles command
├── media/                   uploaded car images (gitignored)
├── .env                     secrets (gitignored)
└── manage.py
```

---

## Setup

### Prerequisites

- Python 3.14
- PostgreSQL running locally
- A Paystack account (test keys are enough)
- A Daraja account at developer.safaricom.co.ke — **register early, sandbox approval can
  take days**

### 1. Virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks the script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### 2. Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Database

Create the database and user in PostgreSQL:

```sql
CREATE DATABASE goldride;
CREATE USER goldride_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE goldride TO goldride_user;
```

### 4. Environment file

Create `.env` in the project root — see [Environment variables](#environment-variables).
It is gitignored and must never be committed.

### 5. Migrate and create an admin account

```powershell
python manage.py migrate
python manage.py createsuperuser
```

### 6. Create the staff roles

```powershell
python manage.py setup_roles
```

### 7. Run

```powershell
python manage.py runserver
```

The API is at `http://127.0.0.1:8000/` and the admin at `http://127.0.0.1:8000/admin/`.

---

## Environment variables

All read via python-decouple. **Never commit `.env`.**

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DATABASE_ENGINE` | `django.db.backends.postgresql` |
| `DATABASE_NAME` | `goldride` |
| `DATABASE_USER` | `goldride_user` |
| `DATABASE_PASSWORD` | database password |
| `DATABASE_HOST` | `localhost` |
| `DATABASE_PORT` | `5432` |
| `PAYSTACK_SECRET_KEY` | `sk_test_...` or `sk_live_...` |
| `PAYSTACK_BASE_URL` | `https://api.paystack.co` — host only, no path |
| `MPESA_ENVIRONMENT` | `sandbox` or `production` |
| `MPESA_CONSUMER_KEY` | from your Daraja app |
| `MPESA_CONSUMER_SECRET` | from your Daraja app |
| `MPESA_SHORTCODE` | `174379` in sandbox |
| `MPESA_PASSKEY` | 64 hex characters |
| `MPESA_CALLBACK_URL` | full public URL to `/api/payments/mpesa/callback/` |

Two things that catch people out:

**`PAYSTACK_BASE_URL` is the host only.** Both the initialize and verify endpoints are
built from it in code. Putting a path here breaks the verify call.

**`MPESA_PASSKEY` is not the same as the Password field.** Daraja's simulator shows a
pre-generated `Password`, which is `base64(shortcode + passkey + timestamp)` and contains
a stale timestamp. Copy the field labelled **Passkey** — 64 lowercase hex characters. The
`Password` is computed fresh on every request by `build_password()`.

---

## API reference

### Public

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/cars/` | 12 per page |
| `GET` | `/api/cars/<id>/` | |
| `POST` | `/api/inquiries/` | 5/hour |
| `GET` | `/api/track/<token>/` | 20/hour |
| `POST` | `/api/payments/initiate/` | 10/hour |

**Car query parameters** — `make`, `model`, `year`, `condition`, `availability`,
`search`, `ordering` (`price`, `-price`, `year`, `-year`), `page`.

```
GET /api/cars/?make=Toyota&condition=used&ordering=-price
```

**Create an enquiry:**

```json
POST /api/inquiries/
{"car": 1, "name": "Jane", "phone": "0712345678", "message": "Still available?"}
```

`car` is the car's id. `message` is optional.

**Start a card payment:**

```json
POST /api/payments/initiate/
{"reference": "<payment uuid>", "email": "customer@example.com"}
```

Returns `{"checkout_url": "..."}`. Note it does **not** accept an amount — that is read
from the database, so a client cannot choose its own price.

### Staff

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/auth/login/` | returns a DRF token |
| `GET` | `/api/inquiries/all/` | requires `Authorization: Token <key>` |

### Provider callbacks — never called directly

| Method | Path | Verified by |
|---|---|---|
| `POST` | `/api/payments/webhook/` | HMAC-SHA512 signature, then a re-query |
| `POST` | `/api/payments/mpesa/callback/` | a re-query (Daraja does not sign) |

---

## The admin

`http://127.0.0.1:8000/admin/` — this is where staff actually work.

**Cars** — details plus a photo gallery inline.

**Inquiries** — read-only in practice; every submission lands here.

**Import orders** — customer details, current stage, and `total_amount`. Milestones and
payments both appear inline. The list shows total, amount paid and balance.

**Payments** — where invoices are raised. Choose the order, set the amount, pick the
method, leave the status `pending`. The `reference` UUID appears after saving; that is
what the customer needs. `reference`, `provider_ref` and `checkout_request_id` are
read-only — they are generated by the system or the provider.

Set a status to `paid` by hand only for **manual** bank transfers. Card and M-PESA
payments update themselves.

---

## Management commands

```powershell
python manage.py payments
```
Lists every payment: reference, amount, method, status, provider reference.

```powershell
python manage.py card_pay <reference> <email>
```
Creates a Paystack checkout link. Safe to run repeatedly on the same payment.

```powershell
python manage.py mpesa_pay <reference> <phone>
```
Sends an STK push. Phone format `2547XXXXXXXX` — no plus sign, no leading zero.

```powershell
python manage.py reconcile_payments
```
Asks both providers what happened to every pending payment and updates those with a
definite answer. Anything still in progress is left alone.

```powershell
python manage.py setup_roles
```
Creates or updates the Sales and Manager groups. Idempotent.

---

## Taking payments

### Card

1. Admin → Payments → Add. Order, amount, method `card`, status `pending`. Save.
2. `python manage.py payments` — copy the reference.
3. `python manage.py card_pay <reference> customer@example.com`
4. Send the customer the checkout link.
5. They pay; Paystack calls the webhook; the row becomes `paid` within seconds.
6. If it does not, run `python manage.py reconcile_payments`.

For Paystack to call the webhook it needs a public URL set in the Paystack dashboard
under **Settings → API Keys & Webhooks**.

**Sandbox test card:** `4084 0840 8408 4081`, CVV `408`, any future expiry, PIN `0000`,
OTP `123456`. It has a low spending limit — large amounts return "Insufficient Funds",
so test with a few thousand shillings.

### M-PESA

M-PESA needs Safaricom to reach your machine, which in development means a tunnel.

1. Start a tunnel:
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
2. Copy the `https://....trycloudflare.com` address it prints. **It changes every restart.**
3. Set `MPESA_CALLBACK_URL` in `.env` to that address plus
   `/api/payments/mpesa/callback/`.
4. **Restart `runserver`.** `.env` is read only at startup — skipping this is the most
   common reason callbacks never arrive.
5. Admin → Payments → Add, method `mpesa`, status `pending`.
6. `python manage.py mpesa_pay <reference> 254712345678`
7. The customer's phone prompts; the window is about 60 seconds.
8. Safaricom calls the callback; the row becomes `paid` with the M-PESA receipt number.

The sandbox test number `254708374149` has no handset behind it and always returns
`1037 timeout`. Use a real Safaricom number to see the prompt.

Settings also need the tunnel host in `ALLOWED_HOSTS`.

### Large payments

M-PESA caps at 250,000 per transaction and 500,000 per day; card limits are lower.
The balance on an expensive car comes by **bank transfer** — record those with method
`manual` and set the status by hand once the money appears on the statement.

---

## Staff roles

`python manage.py setup_roles` creates two groups:

| | Sales | Manager |
|---|---|---|
| Cars and gallery | view, add, change | + delete |
| Inquiries | view | + delete |
| Import orders and milestones | view, add, change | + delete |
| **Payments** | **view only** | view, add, change |

**Nobody gets `delete_payment`.** Financial records outlive convenience — the same
reasoning as `PROTECT` on the foreign key.

Sales cannot create a payment because creating one means setting an amount a customer
will be asked to pay. That is a manager's decision.

To add a staff member: Admin → Users → Add user, tick **Staff status**, leave
**Superuser** off, assign a group. Superusers bypass every permission check, so testing
roles requires a non-superuser account.

---

## Security decisions

These were chosen deliberately. If a change appears to contradict one, question the
change.

1. **Each public door opens one way.** Cars are read-only; inquiries are write-only.
2. **UUID tokens, never sequential IDs.** `/api/track/1/` does not merely fail — the
   route pattern accepts only a UUID, so there is no way to enumerate customers.
3. **The server decides the amount.** `/api/payments/initiate/` accepts a reference and
   nothing else.
4. **`PROTECT` on Payment → ImportOrder.** The database refuses to delete an order that
   has payments.
5. **Money is `DecimalField`, never float.**
6. **Throttling is added to a public write endpoint the same day it is written.**
7. **Secrets live in `.env`**, which is gitignored along with `.env.*`.
8. **The backend never holds money.** It records and orchestrates; Paystack and Safaricom
   collect and settle to the registered business account.
9. **Never trust a callback body.** A signature proves who sent a message, not that it is
   true or fresh. Every payment is confirmed by re-querying the provider before the
   database is written. Daraja does not sign callbacks at all, so there the re-query is
   the only defence.
10. **Webhooks are best-effort.** Reconciliation exists because notifications get lost —
    it has already recovered real payments the webhook missed.

---

## Testing

**There are no automated tests.** Every `tests.py` is an empty stub. Everything below was
verified by hand, and nothing in the project would announce a regression.

Verified manually:

- Car listing, filtering, search, ordering, pagination
- Tracking: valid token 200, random UUID 404, `/track/1/` 404, no PII in the response
- Enquiry creation, and 401 on the staff list without a token
- Paystack webhook: forged signature rejected with 400
- M-PESA callback: a forged "success" accepted politely and ignored, payment unchanged
- Repeat card checkout attempts no longer collide (the `paystack_ref` fix)
- Reconciliation recovering payments the webhook missed
- Role permissions: Sales denied `add_payment`, including by direct URL (403)

`pytest` and `pytest-django` are installed but unconfigured.

The most valuable tests to write first are the four webhook cases: forged signature
rejected, valid success marks paid, replay does nothing, amount mismatch refused. The
amount-mismatch case cannot be produced by hand and needs `unittest.mock`.

---

## Known limitations

- **No automated tests** (above)
- **No customer accounts** — customers hold only a tracking link and a payment reference;
  there is no login, no order history
- **Roles are admin-only** — the API has one staff endpoint and does not distinguish
  Sales from Manager
- **Tokens never expire** and there is no logout endpoint
- **Reconciliation runs manually** — in production it should be scheduled
- **Email prints to the console**; nothing is delivered
- **Media is served from local disk** by Django — development only
- **`DEBUG = True`** and `ALLOWED_HOSTS` contains a tunnel domain. **Not deployable as-is.**
- **Repeat checkout attempts:** only the most recent `paystack_ref` is stored, so a
  customer who pays an older checkout link will not be matched automatically.
  Reconciliation will not find it either. A `PaymentAttempt` table would fix this.
- **M-PESA reconciliation cannot recover a receipt number** — the STK query response does
  not include `MpesaReceiptNumber`; only the callback carries it.

### Roadmap

1. Automated tests for the payments app
2. Customer accounts and a "my orders" view
3. Scheduled reconciliation
4. React frontend
5. Production settings, real email, hosted media
6. M-PESA go-live — needs a real paybill and business registration

---

## Troubleshooting

**A payment is stuck on `pending`**
Run `python manage.py reconcile_payments`. If it reports `success`, the money was
collected and only the notification was lost.

**`could not start payment` (502)**
Paystack rejected the request. Usually the payment is not `pending`, or the amount
exceeds the test card's limit.

**M-PESA `1037`** — nobody answered the prompt in time.
**M-PESA `1032`** — the customer cancelled.
**M-PESA `500.001.1001 Wrong credentials`** — the passkey, shortcode or timestamp used to
build the password does not match the request body.

**No M-PESA callback arrives**
The tunnel is down, `MPESA_CALLBACK_URL` is stale, or `runserver` was not restarted after
editing `.env`. The tunnel's own terminal logs every request it forwards — check there
first to see whether Safaricom reached you at all.

**`is not a valid UUID`**
A shortened reference was used. Copy all 36 characters.

**`Unknown command`**
A management command file is missing, or an `__init__.py` is absent from
`management/` or `management/commands/`. Django discovers commands by filename; a missing
package marker fails silently.

**`DisallowedHost`**
The host is not in `ALLOWED_HOSTS` — add it, then restart.

**PowerShell oddities**
`curl` is an alias for `Invoke-WebRequest` and ignores `-X` and `-d`; use `curl.exe` or
Python. `grep` does not exist; use `Select-String`. Bash-style `\"` escaping inside
`python -c "..."` breaks — put anything needing quotes into a `.py` file.
