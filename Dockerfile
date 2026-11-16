# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    UV_NO_SYNC=1

# Librerie di sistema per WeasyPrint (PDF) e Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 \
        libjpeg62-turbo zlib1g fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# uv (versione fissata; UV_NO_SYNC: `uv run` usa l'ambiente costruito qui, senza
# reinstallare a runtime le dipendenze di sviluppo)
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/

WORKDIR /app

# Dipendenze (layer cache)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen

# Codice
COPY . .

# Statici serviti da WhiteNoise: file e manifest restano nell'immagine, sempre allineati al codice
RUN uv run python manage.py collectstatic --noinput

COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uv", "run", "gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
