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
