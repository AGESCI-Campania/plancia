# apps/storage_drive/tasks.py
"""Task Celery per l'upload asincrono di file su Google Drive."""
from celery import shared_task


@shared_task
def task_carica_allegato_drive(allegato_pk: int) -> dict:
    from apps.diaries.models import Allegato, StatoSync

    try:
        allegato = Allegato.objects.select_related(
            "diario__edizione", "diario__squadriglia__reparto__gruppo__zona"
        ).get(pk=allegato_pk)
    except Allegato.DoesNotExist:
        return {"ok": False, "error": "Allegato non trovato"}

    if allegato.stato_sync == StatoSync.CARICATO:
        return {"ok": True, "skipped": True}

    try:
        from apps.storage_drive.service import carica_allegato_drive

        carica_allegato_drive(allegato)
        return {"ok": True, "drive_file_id": allegato.drive_file_id}
    except Exception as exc:
        # Reimposta a LOCALE per permettere il retry
        Allegato.objects.filter(pk=allegato_pk).update(stato_sync=StatoSync.LOCALE)
        return {"ok": False, "error": str(exc)}
