# apps/exports/tasks.py
"""Task Celery per la generazione asincrona di PDF ed Excel. Vedi docs sez. 11."""
from celery import shared_task


@shared_task
def task_genera_pdf_diario(diario_pk: int) -> dict:
    from apps.diaries.models import Diario
    from apps.exports.service import genera_pdf_diario

    try:
        diario = Diario.objects.get(pk=diario_pk)
    except Diario.DoesNotExist:
        return {"ok": False, "error": "Diario non trovato"}

    pdf_bytes = genera_pdf_diario(diario)

    if diario.edizione.drive_oauth_account:
        try:
            from apps.storage_drive.service import carica_pdf_diario
            carica_pdf_diario(diario)
            return {"ok": True, "size": len(pdf_bytes), "drive": True}
        except Exception as exc:
            return {"ok": True, "size": len(pdf_bytes), "drive": False, "drive_error": str(exc)}

    return {"ok": True, "size": len(pdf_bytes)}


@shared_task
def task_genera_excel_edizione(edizione_pk: int) -> dict:
    from apps.editions.models import Edizione
    from apps.exports.service import genera_excel_edizione

    try:
        edizione = Edizione.objects.get(pk=edizione_pk)
    except Edizione.DoesNotExist:
        return {"ok": False, "error": "Edizione non trovata"}

    excel_bytes = genera_excel_edizione(edizione)

    if edizione.drive_oauth_account:
        try:
            from apps.storage_drive.service import carica_excel_edizione
            carica_excel_edizione(edizione)
            return {"ok": True, "size": len(excel_bytes), "drive": True}
        except Exception as exc:
            return {"ok": True, "size": len(excel_bytes), "drive": False, "drive_error": str(exc)}

    return {"ok": True, "size": len(excel_bytes)}
