#!/bin/sh
# Entrypoint comune a web, worker, beat e flower. Solo il web (ESEGUI_MIGRAZIONI=1 nel
# compose) applica le migrazioni, così i container non le eseguono in parallelo.
set -e

if [ "${ESEGUI_MIGRAZIONI:-0}" = "1" ]; then
    echo ">>> migrate"
    uv run python manage.py migrate --noinput
fi

exec "$@"
