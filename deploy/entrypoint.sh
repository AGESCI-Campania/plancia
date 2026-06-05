#!/bin/sh
# Entrypoint del container web: esegue le migrazioni prima di avviare gunicorn.
set -e

echo ">>> migrate"
uv run python manage.py migrate --noinput

echo ">>> starting gunicorn"
exec "$@"
