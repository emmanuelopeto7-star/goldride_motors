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
