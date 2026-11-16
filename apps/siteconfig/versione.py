"""Versione del server installata, letta da `pyproject.toml` (in container: `/app/pyproject.toml`)."""
from __future__ import annotations

import functools
import tomllib

from django.conf import settings


@functools.cache
def versione_installata() -> str:
    """Versione `X.Y.Z` dichiarata in `pyproject.toml` ("?" se il file non è leggibile).

    In cache per tutta la vita del processo: la versione cambia solo con una nuova immagine,
    cioè con il riavvio dei container. `versione_installata.cache_clear()` nei test.
    """
    try:
        with open(settings.BASE_DIR / "pyproject.toml", "rb") as f:
            return str(tomllib.load(f).get("project", {}).get("version") or "?")
    except (OSError, tomllib.TOMLDecodeError):
        return getattr(settings, "APP_VERSION", "") or "?"
