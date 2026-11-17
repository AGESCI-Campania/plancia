# syntax=docker/dockerfile:1
FROM python:3.14.10-slim-trixie AS base

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

# Utente non root con uid/gid del proprietario del repo sull'host (agesci), passati dagli
# script: i file scritti nei bind mount (logs/, aggiornamenti/) restano suoi.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --non-unique --gid "$APP_GID" plancia \
    && useradd --non-unique --uid "$APP_UID" --gid "$APP_GID" --home-dir /home/plancia --create-home plancia

WORKDIR /app

# Dipendenze (layer cache)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen

# Codice
COPY . .

# Statici serviti da WhiteNoise: file e manifest restano nell'immagine, sempre allineati al codice
RUN uv run python manage.py collectstatic --noinput

COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/logs/email /app/media \
    && chown -R plancia:plancia /app/logs /app/media

USER plancia

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uv", "run", "gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
