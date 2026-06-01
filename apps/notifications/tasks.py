# apps/notifications/tasks.py
"""Task Celery per l'invio asincrono di email. Vedi docs sez. 8."""
from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def task_invia_invito(self, invito_pk: int) -> dict:
    from apps.notifications.models import Invito
    from apps.notifications.service import invia_invito

    try:
        invito = Invito.objects.get(pk=invito_pk)
    except Invito.DoesNotExist:
        return {"ok": False, "error": "Invito non trovato"}

    ok = invia_invito(invito)
    if not ok:
        raise self.retry(exc=Exception("Invio fallito"))
    return {"ok": True, "invito_pk": invito_pk}


@shared_task
def task_invia_inviti_bulk(diario_pk: int, ruoli: list[str]) -> dict:
    """Invia tutti gli inviti mancanti per un diario."""
    from apps.diaries.models import Diario
    from apps.notifications.service import crea_e_invia_invito

    try:
        diario = Diario.objects.select_related("csq__utente", "crp__utente").get(pk=diario_pk)
    except Diario.DoesNotExist:
        return {"ok": False}

    inviati = 0
    for ruolo in ruoli:
        socio = diario.csq if ruolo == "csq" else diario.crp
        if socio and hasattr(socio, "utente") and socio.utente:
            crea_e_invia_invito(diario, socio.utente, ruolo)
            inviati += 1
    return {"ok": True, "inviati": inviati}
