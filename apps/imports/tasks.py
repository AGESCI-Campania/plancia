# apps/imports/tasks.py
"""Task Celery per avviare i management command di import. Vedi docs sez. 14."""
from __future__ import annotations

import contextlib
import io
import logging
import os

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def task_import_risposte_eg(
    self,
    file_path: str,
    edizione_pk: int | None = None,
    solo_staff: bool = False,
    solo_eg: bool = False,
) -> dict:
    """Importa diari da Excel Jotform (Risposte EG + Risposte staff) in modo asincrono.

    Invia email agli Admin all'avvio e al completamento con l'output completo.
    """
    import io
    import os

    from django.core.mail import EmailMultiAlternatives
    from django.core.management import call_command

    from apps.accounts.models import Ruolo, User
    from apps.siteconfig.email_backends import get_connection_per_tipo
    from apps.siteconfig.models import Impostazioni

    imp = Impostazioni.get()
    conn = get_connection_per_tipo("standard")
    nome_file = os.path.basename(file_path)

    admin_emails = list(
        User.objects.filter(ruolo=Ruolo.ADMIN).exclude(email="").values_list("email", flat=True)
    )

    def _mail(soggetto: str, corpo: str) -> None:
        if not admin_emails:
            return
        with contextlib.suppress(Exception):
            EmailMultiAlternatives(
                subject=soggetto, body=corpo,
                from_email=imp.from_email, to=admin_emails, connection=conn,
            ).send()

    # Email di avvio
    _mail(
        f"[Plancia] Import Risposte EG avviato — {nome_file}",
        f"L'import Risposte EG è stato avviato.\n\n"
        f"File: {nome_file}\n"
        f"Edizione: {edizione_pk or 'più recente aperta'}\n"
        f"Fogli: {'solo Risposte staff' if solo_staff else 'solo Risposte EG' if solo_eg else 'entrambi'}\n",
    )

    out = io.StringIO()
    err = io.StringIO()
    ok = False
    output = ""

    try:
        kwargs: dict = {"stdout": out, "stderr": err, "verbosity": 1}
        if edizione_pk:
            kwargs["edizione"] = edizione_pk
        if solo_staff:
            kwargs["solo_staff"] = True
        if solo_eg:
            kwargs["solo_eg"] = True
        call_command("import_risposte_eg", file_path, **kwargs)
        ok = True
        output = out.getvalue()
        logger.info("Import risposte_eg completato: %s", output[:500])
    except Exception as exc:
        output = f"Errore: {exc}\n{err.getvalue()}"
        logger.exception("Errore import risposte_eg: %s", exc)
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    stato = "completato" if ok else "terminato con ERRORI"
    _mail(
        f"[Plancia] Import Risposte EG {stato} — {nome_file}",
        f"Import Risposte EG {stato}.\n\n"
        f"File: {nome_file}\n\n"
        f"Output:\n{'-' * 60}\n{output}\n{'-' * 60}",
    )

    return {"ok": ok, "output": output}


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
