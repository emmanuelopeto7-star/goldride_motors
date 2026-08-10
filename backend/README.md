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

### 4. Add your own credentials

Create a file named `.env` in the project root. The project reads its settings from
there, and it is gitignored — **never commit it.**

It needs entries for:

- **Django** — a secret key, a debug flag, and the allowed hosts
- **Paystack** — your secret key and the API base URL
- **M-PESA** — your Daraja consumer key and secret, the shortcode, the passkey, the
  environment, and your callback URL

Use your own credentials. Paystack keys come from your Paystack dashboard; the M-PESA
values come from your own Daraja app. Generate a Django secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

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




## Known limitations

- **No automated tests.** Everything has been checked by hand.
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
