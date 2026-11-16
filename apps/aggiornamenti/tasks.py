"""Task Celery degli aggiornamenti (schedulato da Celery beat: `CELERY_BEAT_SCHEDULE`)."""
from __future__ import annotations

from celery import shared_task


@shared_task(name="aggiornamenti.controlla_ultima_release", ignore_result=True)
def controlla_ultima_release() -> str:
    """Controllo giornaliero dell'ultima release GitHub. Non solleva eccezioni."""
    from apps.aggiornamenti.services import controlla_ultima_release as controlla

    return controlla().versione
