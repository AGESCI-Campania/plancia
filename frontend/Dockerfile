# syntax=docker/dockerfile:1
# Immagine dell'nginx interno di Plancia: la SPA costruita (frontend/dist) + il proxy verso
# Django. Contesto di build: la radice del repo (serve ../pyproject.toml per la versione).

FROM node:26.13.1-alpine3.24 AS build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY pyproject.toml /src/pyproject.toml
COPY docs/icona-pwa /src/docs/icona-pwa
COPY frontend/ ./
# Solo la build di Vite: il typecheck (vue-tsc) si fa in sviluppo e nei test, qui costa memoria
RUN npx vite build

FROM nginx:1.30.6-alpine
COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY deploy/nginx/proxy-django.inc /etc/nginx/conf.d/proxy-django.inc
COPY --from=build /src/frontend/dist /usr/share/nginx/html
