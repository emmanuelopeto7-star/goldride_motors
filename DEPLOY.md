# Deploying Goldride Motors

Host-neutral on purpose. Everything below is a property of the application, not
of any particular platform — pick a host and map these onto it.

## The two commands

```
Build:  bash build.sh
Start:  cd backend && daphne -b 0.0.0.0 -p $PORT goldride_project.asgi:application
```

**Daphne, not gunicorn.** gunicorn is WSGI and cannot carry a websocket at all.
Under it the chat handshake fails and the browser retries forever, with nothing
useful in the logs to say why. `gunicorn` is still in `requirements.txt`; it is
unused.

`build.sh` installs requirements, runs `collectstatic` before `migrate`, and
uses `set -o errexit` so a failed migration fails the build rather than starting
a half-deployed service over a healthy release.

## Environment

| Variable | Why it has no default |
|---|---|
| `SECRET_KEY` | Session and token signing. |
| `DEBUG` | **Must be `false`.** See the warning below. |
| `DATABASE_URL` | Falls back to local SQLite otherwise. |
| `ALLOWED_HOSTS` | Comma-separated. `PUBLIC_HOSTNAME` is merged in as well, for hosts that inject the public hostname rather than letting you name it. |
| `PAYSTACK_SECRET_KEY` | Card payments and every webhook signature check. |
| `MPESA_*` | Consumer key/secret, shortcode, passkey, callback URL, environment. |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Without these Django uses the console backend and **every message the app sends reaches nobody**. |
| `DEFAULT_FROM_EMAIL` | The address customers see. |
| `SITE_URL` | Where `/pay/<reference>/` links point — the backend's own origin. |
| `FRONTEND_URL` | Where tracking, account and chat links in emails point. |
| `CORS_ALLOWED_ORIGINS` | Defaults to localhost ports only. |
| `REDIS_URL` | Without it the channel layer is in-memory and per-process: with more than one worker, a chat message broadcast by one is invisible to anybody connected to another. |
| `RECONCILE_INTERVAL_MINUTES` | How often the in-process sweep runs. `0` switches it off, for when an external scheduler runs the command instead. |

`CSRF_TRUSTED_ORIGINS` is derived from `ALLOWED_HOSTS` with an `https://`
scheme — Django rejects cross-origin POSTs without that, admin login included.
`SECURE_PROXY_SSL_HEADER` trusts `X-Forwarded-Proto`, so the app **must** sit
behind a proxy that sets it; exposed directly, a client could send that header
itself and be believed.

## Mail

Once the SMTP variables are set:

```bash
python manage.py mailtest you@example.com
```

It reports which backend is live and whether delivery was accepted. Every send
goes through `goldride_app/mail.py`, which logs failures rather than swallowing
them — the previous code passed `fail_silently=True` everywhere, so a
misconfigured server looked exactly like a working one.

Add SPF and DKIM records for `goldridemotors.co.ke`, or mail from `noreply@`
lands in spam.

## Payment reconciliation

Webhooks get dropped. Reconciliation asks each provider what actually happened
to every pending payment, and it has already caught real payments that were
taken and never recorded against an order — so it is not a refresh button.

It runs **inside the application**, on a background thread started with the
server, every `RECONCILE_INTERVAL_MINUTES` (default 30). No external scheduler
is required, and nothing about it is host-specific. Concurrent workers are
handled: each sweep claims a lock row in the database, so with four workers only
one sweeps and the rest move on.

The same work is available as a command, for an external scheduler or by hand:

```bash
python manage.py reconcile_payments
```

Set `RECONCILE_INTERVAL_MINUTES=0` if you schedule it that way, so it does not
run twice.

Frequency is not what keeps a live checkout safe: Paystack reports an
initialised-but-unpaid transaction as `abandoned` immediately, and
`ABANDONED_GRACE` (30 minutes, in `payments/reconciliation.py`) is what stops a
checkout somebody is still paying from being marked failed, at any cadence.

Every status change a payment has ever had is recorded as a `PaymentEvent` —
what changed it, when, and who, if a person was involved. Staff read it on the
payments screen; a manager can correct a mistaken status there, and the
correction is another event rather than an overwrite.

## Media

**Turning `DEBUG` off loses every car photograph** unless media has a home
first. Confirmed under Daphne with `DEBUG=false`: the API answers, the admin
serves its own hashed stylesheet, a websocket connects — and `/media/...`
returns 404. Two reasons: `django.conf.urls.static.static()` serves nothing with
debug off, and WhiteNoise deliberately refuses user uploads.

So production needs one of:

* a persistent disk mounted at `backend/media/`, served by the proxy in front
  of the app; or
* object storage (S3, Cloudinary — neither is currently a dependency).

Both cost money, which is why this is a decision rather than a task. Note that
an ephemeral filesystem loses uploads on every deploy even when they are served,
so "no disk" is not a middle option.

Dealer paperwork is **not** affected and must never be moved into a public media
path: those files are streamed by a staff-only view that checks the caller
first. See `dealers/models.py`.

## Static files

WhiteNoise with `ManifestStaticFilesStorage`, `STATIC_ROOT` collected at build
time. The manifest refuses to start if anything referenced is missing, which is
why `collectstatic` runs before `migrate` — a missing asset fails the build
rather than a request.

## Deployment checks

```bash
DEBUG=false SECURE_HTTPS=true python manage.py check --deploy
```

Clean apart from `security.W021` (HSTS preload), which is declined deliberately
in a comment in `settings.py`: preloading ships the domain inside browsers
themselves and getting removed takes months — not something to enable at a
one-hour `SECURE_HSTS_SECONDS`. That max-age is also deliberately low, and meant
to be raised by hand once HTTPS has been reliable for a while.

## Frontend

Not deployed yet. `VITE_API_URL` still points at `http://localhost:8000`, so a
deployed frontend would call a developer's laptop. Where it is hosted has not
been decided.
