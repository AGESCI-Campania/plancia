# apps/siteconfig/axes_helpers.py
"""Callable lette da django-axes per ricavare failure_limit e cooloff da DB."""
from __future__ import annotations

from datetime import timedelta

from django.http import HttpRequest


def axes_failure_limit(request: HttpRequest, credentials: dict) -> int:
    """Numero massimo di tentativi falliti prima del blocco (da Impostazioni)."""
    from apps.siteconfig.models import Impostazioni
    return Impostazioni.get().axes_failure_limit


def axes_cooloff_time(request: HttpRequest | None = None) -> timedelta | None:
    """Durata del blocco automatico (da Impostazioni). None = blocco permanente."""
    from apps.siteconfig.models import Impostazioni
    minutes = Impostazioni.get().axes_cooloff_minutes
    if minutes:
        return timedelta(minutes=minutes)
    return None


def ip_client_dietro_proxy(request: HttpRequest) -> str | None:
    """IP del client in produzione (Caddy → nginx interno → gunicorn).

    REMOTE_ADDR è l'nginx interno, uguale per tutti: bloccare per IP su quello
    bloccherebbe chiunque. Caddy imposta X-Forwarded-For con l'IP del client
    (ignora quello ricevuto da fuori) e nginx vi aggiunge l'IP di Caddy, quindi il
    client è il penultimo elemento. Senza intestazione (accesso diretto) si usa REMOTE_ADDR.
    """
    voci = [v.strip() for v in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if v.strip()]
    if len(voci) >= 2:
        return voci[-2]
    return request.META.get("REMOTE_ADDR")
