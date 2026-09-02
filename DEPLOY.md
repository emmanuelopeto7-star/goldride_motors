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
| `EMAIL_BACKEND`, `RESEND_API_KEY` | Without these Django uses the console backend and **every message the app sends reaches nobody**. See Mail below. |
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

Mail goes through **Resend over HTTPS**, not SMTP:

```
EMAIL_BACKEND=goldride_app.email_backends.ResendBackend
RESEND_API_KEY=re_...
DEFAULT_FROM_EMAIL=noreply@goldridemotors.co.ke
```

HTTPS rather than SMTP on purpose — managed hosts block outbound SMTP far more
often than they block an ordinary API call, and that is a bad thing to discover
after everything else is wired. Django's SMTP backend still works if you would
rather use it: point `EMAIL_BACKEND` at
`django.core.mail.backends.smtp.EmailBackend` and set the `EMAIL_HOST` group
(Resend's SMTP host is `smtp.resend.com`, username the literal `resend`, the
API key as the password).

Then:

```bash
python manage.py mailtest you@example.com
```

It reports which backend is live and whether delivery was accepted. Every send
goes through `goldride_app/mail.py`, which logs failures rather than swallowing
them — the previous code passed `fail_silently=True` everywhere, so a
misconfigured server looked exactly like a working one.

**The from-address domain must be verified in Resend**, and Resend will not
send from an unverified one. Verifying it is also how SPF and DKIM get set up
for `goldridemotors.co.ke` — Resend generates the exact DNS records. Without
them, mail from `noreply@` lands in spam. `onboarding@resend.dev` sends without
any of that but delivers only to your own Resend account address, so it is for
testing and nothing else.

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

**Currently deployed without either**, on Render's free plan: `render.yaml`
mounts no disk, so `/media/` returns 404 in production and car photographs do
not appear. That is a known, accepted state for now, not a bug to hunt.

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

Vercel, from `frontend/`. Set the project's **Root Directory** to `frontend` —
the repository root holds no application, and Vercel will otherwise try to build
the container.

`vercel.json` rewrites everything except `/assets/` to `index.html`. Without it
react-router's own URLs — `/staff/overview`, `/cars/12`, `/dealer` — return 404
on refresh or when opened directly, because Vercel looks for a file at that path.

Environment variables (Production scope):

| Variable | Value |
|---|---|
| `VITE_API_URL` | the Render service's `https://` URL, no trailing slash |
| `VITE_GOOGLE_CLIENT_ID` | same value as the backend's |
| `VITE_LINKEDIN_REDIRECT_URI` | `https://<vercel-domain>/auth/linkedin/callback` |

**These are baked into the bundle at build time, not read at runtime.** Changing
one in the Vercel dashboard does nothing until you redeploy. The websocket URL
is derived from `VITE_API_URL` in `lib/socket.js`, so there is no second address
to keep in step — but it also means a wrong `VITE_API_URL` breaks chat and the
API together.

## Order of deployment

The two halves each need the other's URL, so it takes three passes:

1. **Backend first**, with `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL` left unset.
   Nothing can call it yet; that is fine. Note the URL it gets.
2. **Frontend**, with `VITE_API_URL` set to that URL.
3. **Back to the backend**: set `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL` to the
   Vercel domain and redeploy. Until this pass the browser blocks every request
   as cross-origin, and the app looks broken in a way the logs do not explain.

Then, outside both dashboards: add the Vercel domain to the Google OAuth client's
**Authorized JavaScript origins**, and `https://<vercel-domain>/auth/linkedin/callback`
to LinkedIn's redirect URLs. Sign-in fails with a provider-side error otherwise.
