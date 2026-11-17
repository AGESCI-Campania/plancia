"""Modalità manutenzione: stesso flag letto da `MaintenanceModeMiddleware` (`Impostazioni.manutenzione`).

Usata dal comando `manage.py manutenzione` (e quindi da `scripts/aggiorna.sh`) e da `GET /api/v1/sito`.
"""
from __future__ import annotations

MESSAGGIO_PREDEFINITO = "Servizio in manutenzione. Riprovare più tardi."


def manutenzione_attiva() -> bool:
    """Legge il flag direttamente dal database (non dalla cache): serve agli script."""
    from apps.siteconfig.models import Impostazioni

    return bool(
        Impostazioni.objects.filter(pk=1).values_list("manutenzione", flat=True).first()
    )


def imposta_manutenzione(attiva: bool, messaggio: str | None = None) -> None:
    """Attiva/disattiva la manutenzione; `messaggio` (se dato) sostituisce quello mostrato.

    Rilegge la riga dal DB invece di usare la copia in cache, così non sovrascrive con
    valori vecchi le altre impostazioni; `save()` aggiorna anche la cache condivisa.
    """
    from apps.siteconfig.models import Impostazioni

    imp, _ = Impostazioni.objects.get_or_create(pk=1)
    imp.manutenzione = attiva
    campi = ["manutenzione", "aggiornato_at"]
    if messaggio is not None:
        imp.manutenzione_messaggio = messaggio
        campi.append("manutenzione_messaggio")
    imp.save(update_fields=campi)


def messaggio_manutenzione(imp) -> str:
    return (getattr(imp, "manutenzione_messaggio", "") or "").strip() or MESSAGGIO_PREDEFINITO
