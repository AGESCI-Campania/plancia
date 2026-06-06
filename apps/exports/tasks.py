# apps/exports/tasks.py
"""Task Celery per la generazione asincrona di PDF ed Excel. Vedi docs sez. 11."""
from celery import shared_task


@shared_task
def task_genera_pdf_diario(diario_pk: int, utente_pk: int | None = None) -> dict:
    """Genera il PDF del diario, lo carica su Drive e notifica l'utente per email."""
    from apps.diaries.models import Diario
    from apps.exports.service import genera_pdf_diario

    try:
        diario = Diario.objects.select_related(
            "edizione", "squadriglia__reparto__gruppo__zona", "csq",
        ).get(pk=diario_pk)
    except Diario.DoesNotExist:
        return {"ok": False, "error": "Diario non trovato"}

    try:
        genera_pdf_diario(diario)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    drive_ok = False
    if diario.edizione.drive_oauth_account:
        try:
            from apps.storage_drive.service import carica_pdf_diario
            carica_pdf_diario(diario)
            drive_ok = True
        except Exception as exc:
            return {"ok": True, "drive": False, "drive_error": str(exc)}

    if utente_pk and drive_ok:
        _invia_mail_pdf("diario_pdf_pronto", utente_pk, diario)

    return {"ok": True, "drive": drive_ok}


def _invia_mail_pdf(chiave: str, utente_pk: int, diario, link_pdf: str = "") -> None:
    """Invia email all'utente relativa alla generazione del PDF.

    chiave: 'diario_pdf_in_generazione' oppure 'diario_pdf_pronto'.
    Se link_pdf è vuoto viene costruito da BASE_URL.
    """
    try:
        from django.conf import settings
        from django.core.mail import EmailMultiAlternatives
        from django.urls import reverse

        from apps.accounts.models import User
        from apps.notifications.models import render_mail
        from apps.siteconfig.email_backends import get_connection_per_tipo
        from apps.siteconfig.models import Impostazioni

        utente = User.objects.filter(pk=utente_pk).first()
        if not utente or not utente.email:
            return

        imp = Impostazioni.get()

        if not link_pdf and chiave == "diario_pdf_pronto":
            base_url = getattr(settings, "BASE_URL", "https://plancia.agescicampania.org").rstrip("/")
            link_pdf = f"{base_url}{reverse('diaries:pdf', args=[diario.pk])}"

        oggetto, corpo = render_mail(chiave, {
            "nome": utente.first_name or utente.email,
            "cognome": utente.last_name or "",
            "titolo_piattaforma": imp.titolo or "Plancia",
            "squadriglia": str(diario.squadriglia),
            "link_pdf": link_pdf,
        })

        soggetti_default = {
            "diario_pdf_in_generazione": f"PDF in generazione — {diario.squadriglia}",
            "diario_pdf_pronto": f"PDF pronto — {diario.squadriglia}",
        }
        msg = EmailMultiAlternatives(
            subject=oggetto or soggetti_default.get(chiave, "Notifica PDF"),
            body=corpo,
            from_email=imp.from_email,
            to=[utente.email],
            connection=get_connection_per_tipo("standard"),
        )
        msg.attach_alternative(corpo, "text/html")
        msg.send()
    except Exception:
        pass  # la notifica non è critica


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
