# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# Librerie di sistema per WeasyPrint (PDF) e Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 \
        libjpeg62-turbo zlib1g fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dipendenze (layer cache)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Codice
COPY . .

RUN uv run python manage.py collectstatic --noinput || true

EXPOSE 8000
CMD ["uv", "run", "gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--workers", "3"]
