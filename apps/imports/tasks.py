# apps/imports/tasks.py
"""Task Celery per avviare i management command di import. Vedi docs sez. 14."""
from __future__ import annotations

import io
import logging
import os

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def task_lancia_import(tracciato: str, path: str = "", edizione_pk: int | None = None) -> dict:
    """Avvia l'import come task Celery (chiamato da UI/admin).

    Il file CSV deve essere già salvato su filesystem al percorso `path`.
    La UI salva il file caricato in MEDIA_ROOT/imports/tmp/ prima di accodare il task.
    """
    from django.core.management import call_command

    logger.info("Import %s avviato (path=%s, edizione_pk=%s)", tracciato, path, edizione_pk)

    if not os.path.exists(path):
        msg = f"File non trovato: {path}"
        logger.error(msg)
        return {"ok": False, "error": msg}

    out = io.StringIO()
    err = io.StringIO()

    try:
        if tracciato == "squadriglie":
            if not edizione_pk:
                return {"ok": False, "error": "edizione_pk obbligatorio per import squadriglie"}
            call_command("import_squadriglie", path, f"--edizione={edizione_pk}", stdout=out, stderr=err)
        elif tracciato == "coca":
            call_command("import_coca", path, stdout=out, stderr=err)
        elif tracciato == "ragazzi":
            call_command("import_ragazzi", path, stdout=out, stderr=err)
        else:
            return {"ok": False, "error": f"Tracciato '{tracciato}' non riconosciuto"}
    except Exception as exc:
        logger.exception("Errore durante import %s: %s", tracciato, exc)
        return {"ok": False, "error": str(exc)}

    logger.info("Import %s completato. Output: %s", tracciato, out.getvalue()[:500])
    return {"ok": True, "output": out.getvalue()}
