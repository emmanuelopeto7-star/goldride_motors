#!/usr/bin/env bash
# What runs before the service starts, on any host.
#
# errexit matters more than usual here: without it a failed migration or a
# missing static file would be logged and then the service would start anyway,
# serving a half-deployed site. Better to fail the build and keep the previous
# release running.
set -o errexit

# Lives in backend/ rather than at the root: a requirements.txt beside a
# manage.py is what makes Vercel decide the repository is a Django project
# and try to build the API instead of the site.
pip install -r backend/requirements.txt

cd backend

# Before migrate, so a missing asset fails the build rather than a request.
# ManifestStaticFilesStorage refuses to start if anything referenced is absent.
python manage.py collectstatic --no-input

python manage.py migrate

# Roles, every time. `get_or_create`, so re-running changes nothing - and the
# permission classes check group membership, meaning without these even a
# superuser cannot open the staff screens.
python manage.py setup_roles

# The first admin. This lives here because Render's free plan has no shell, so
# there is otherwise no way to create one at all. It runs only when the
# credentials are supplied, and `|| true` covers the case where the account
# already exists - createsuperuser exits non-zero then, and errexit would fail
# an otherwise healthy deploy.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput || true
fi
