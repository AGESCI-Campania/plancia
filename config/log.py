"""Filtri di logging."""

import logging


def non_manutenzione(record: logging.LogRecord) -> bool:
    """Scarta le risposte 503: le dà la manutenzione, voluta durante gli aggiornamenti; senza
    filtro ogni richiesta (es. la SPA che riprova l'API) manda una email agli amministratori."""
    return getattr(record, "status_code", None) != 503
