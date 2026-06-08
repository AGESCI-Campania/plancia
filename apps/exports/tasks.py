# apps/exports/tasks.py
"""Task Celery per la generazione asincrona di PDF ed Excel. Vedi docs sez. 11."""
import traceback as tb_module

from celery import shared_task


@shared_task
def task_genera_pdf_diario(diario_pk: int, utente_pk: int | None = None) -> dict:
    """Genera il PDF del diario, lo carica su Drive e notifica l'utente per email."""
    from django.core.cache import cache

    from apps.diaries.models import Diario
    from apps.exports.models import LogTaskExport
    from apps.exports.service import genera_pdf_diario

    lock_key = f"pdf_task_lock:{diario_pk}"
    diario_str = f"diario pk={diario_pk}"
    utente_str = f"pk={utente_pk}" if utente_pk else ""

    try:
        diario = Diario.objects.select_related(
            "edizione", "squadriglia__reparto__gruppo__zona", "csq",
        ).get(pk=diario_pk)
        diario_str = str(diario.squadriglia)
    except Diario.DoesNotExist:
        cache.delete(lock_key)
        LogTaskExport.objects.create(
            tipo=LogTaskExport.Tipo.PDF, stato=LogTaskExport.Stato.ERRORE,
            messaggio="Diario non trovato",
            diario_pk=diario_pk, diario_str=diario_str,
            utente_pk=utente_pk, utente_str=utente_str,
        )
        return {"ok": False, "error": "Diario non trovato"}

    if utente_pk:
        from apps.accounts.models import User
        u = User.objects.filter(pk=utente_pk).first()
        if u:
            utente_str = f"{u.get_full_name()} <{u.email}>"

    # PDF = moduli CSQ (1–5) + relazione CRP (6). Mai la valutazione.
    try:
        genera_pdf_diario(diario, include_relazione=True)
    except Exception as exc:
        traceback_str = tb_module.format_exc()
        LogTaskExport.objects.create(
            tipo=LogTaskExport.Tipo.PDF, stato=LogTaskExport.Stato.ERRORE,
            messaggio=str(exc), traceback_testo=traceback_str,
            diario_pk=diario_pk, diario_str=diario_str,
            utente_pk=utente_pk, utente_str=utente_str,
        )
        _notifica_errore_pdf(utente_pk, diario, str(exc), traceback_str)
        return {"ok": False, "error": str(exc)}
    finally:
        cache.delete(lock_key)

    drive_ok = False
    if diario.edizione.drive_oauth_account:
        try:
            from apps.storage_drive.service import carica_pdf_diario
            carica_pdf_diario(diario)
            drive_ok = True
        except Exception as exc:
            traceback_str = tb_module.format_exc()
            LogTaskExport.objects.create(
                tipo=LogTaskExport.Tipo.PDF, stato=LogTaskExport.Stato.ERRORE,
                messaggio=f"Errore upload Drive: {exc}", traceback_testo=traceback_str,
                diario_pk=diario_pk, diario_str=diario_str,
                utente_pk=utente_pk, utente_str=utente_str,
            )
            _notifica_errore_pdf(utente_pk, diario, f"Errore upload Drive: {exc}", traceback_str)
            return {"ok": True, "drive": False, "drive_error": str(exc)}

    LogTaskExport.objects.create(
        tipo=LogTaskExport.Tipo.PDF, stato=LogTaskExport.Stato.OK,
        messaggio=f"PDF generato. Drive: {'caricato' if drive_ok else 'non configurato'}",
        diario_pk=diario_pk, diario_str=diario_str,
        utente_pk=utente_pk, utente_str=utente_str,
    )

    if utente_pk and drive_ok:
        _invia_mail_pdf("diario_pdf_pronto", utente_pk, diario)

    return {"ok": True, "drive": drive_ok}


def _notifica_errore_pdf(utente_pk: int | None, diario, errore: str, traceback_str: str) -> None:
    """Notifica il richiedente e gli admin dell'errore nella generazione PDF."""
    try:
        from django.conf import settings
        from django.core.mail import EmailMultiAlternatives

        from apps.accounts.models import Ruolo, User
        from apps.siteconfig.email_backends import get_connection_per_tipo
        from apps.siteconfig.models import Impostazioni

        imp = Impostazioni.get()
        base_url = getattr(settings, "BASE_URL", "https://plancia.agescicampania.org").rstrip("/")
        conn = get_connection_per_tipo("standard")

        if utente_pk:
            utente = User.objects.filter(pk=utente_pk).first()
            if utente and utente.email:
                msg = EmailMultiAlternatives(
                    subject=f"Errore generazione PDF — {diario.squadriglia}",
                    body=(
                        f"Ciao {utente.first_name or utente.email},\n\n"
                        f"Si è verificato un errore durante la generazione del PDF "
                        f"per la squadriglia {diario.squadriglia}.\n\n"
                        f"Errore: {errore}\n\n"
                        f"Il team tecnico è stato avvisato. "
                        f"Puoi riprovare dalla pagina del diario."
                    ),
                    from_email=imp.from_email,
                    to=[utente.email],
                    connection=conn,
                )
                msg.send()

        admin_emails = list(
            User.objects.filter(ruolo=Ruolo.ADMIN)
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if admin_emails:
            corpo_admin = (
                f"Errore nella generazione del PDF\n\n"
                f"Diario: {diario.squadriglia} (pk={diario.pk})\n"
                f"Edizione: {diario.edizione}\n"
                f"Errore: {errore}\n\n"
                f"Traceback:\n{traceback_str}\n\n"
                f"Log: {base_url}/impostazioni/#log-export"
            )
            msg_admin = EmailMultiAlternatives(
                subject=f"[Plancia] Errore PDF — {diario.squadriglia}",
                body=corpo_admin,
                from_email=imp.from_email,
                to=admin_emails,
                connection=conn,
            )
            msg_admin.send()
    except Exception:
        pass  # la notifica non è critica


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


# ---------------------------------------------------------------------------
# Chiave Redis per il lock della generazione massiva
# ---------------------------------------------------------------------------

def lock_key_massivo(edizione_pk: int) -> str:
    return f"pdf_massivo_lock:{edizione_pk}"


@shared_task(bind=True, max_retries=0)
def task_genera_pdf_massivo(self, edizione_pk: int, utente_pk: int | None = None) -> dict:
    """Genera i PDF di tutti i diari pubblicabili di un'edizione.

    Flusso:
    1. Email di avvio al richiedente
    2. Email di progresso ogni 10 diari con i link ai PDF già generati
    3. Email finale con tutti i link
    4. Log in LogTaskExport (tipo=PDF_MASSIVO)

    Durante l'esecuzione imposta il lock pdf_massivo_lock:{edizione_pk} che
    impedisce la generazione di singoli PDF per i diari dell'edizione.
    """
    import traceback as tb_module

    from django.conf import settings
    from django.core.cache import cache
    from django.core.mail import EmailMultiAlternatives

    from apps.accounts.models import Ruolo, User
    from apps.editions.models import Edizione
    from apps.exports.models import LogTaskExport
    from apps.exports.service import genera_pdf_diario
    from apps.siteconfig.email_backends import get_connection_per_tipo
    from apps.siteconfig.models import Impostazioni

    lock_key = lock_key_massivo(edizione_pk)
    base_url = getattr(settings, "BASE_URL", "https://plancia.agescicampania.org").rstrip("/")

    try:
        edizione = Edizione.objects.get(pk=edizione_pk)
    except Edizione.DoesNotExist:
        cache.delete(lock_key)
        return {"ok": False, "error": "Edizione non trovata"}

    edizione_str = str(edizione)
    utente_str = ""
    utente = None
    if utente_pk:
        utente = User.objects.filter(pk=utente_pk).first()
        if utente:
            utente_str = f"{utente.get_full_name()} <{utente.email}>"

    imp = Impostazioni.get()
    conn = get_connection_per_tipo("standard")

    def _mail(subject: str, body: str, to: list[str]) -> None:
        try:
            EmailMultiAlternatives(
                subject=subject, body=body, from_email=imp.from_email, to=to, connection=conn,
            ).send()
        except Exception:
            pass

    # --- stati dei diari da includere (inviati o oltre) ----------------------
    from apps.diaries.models import Diario, StatoDiario

    stati_inclusi = [
        StatoDiario.INVIATO, StatoDiario.IN_VALUTAZIONE, StatoDiario.IN_REVISIONE,
        StatoDiario.APPROVATO, StatoDiario.NON_APPROVATO, StatoDiario.MAGGIORI_INFO,
    ]
    diari = list(
        Diario.objects.filter(edizione=edizione, stato__in=stati_inclusi)
        .select_related("squadriglia__reparto__gruppo__zona", "edizione", "csq")
        .order_by("squadriglia__reparto__gruppo__zona__nome", "squadriglia__nome")
    )

    totale = len(diari)

    # Salva task_id in Redis per il polling del progresso dalla UI
    cache.set(f"pdf_massivo_task_id:{edizione_pk}", self.request.id, 7200)
    self.update_state(state="PROGRESS", meta={"progresso": 0, "completati": 0, "totale": totale})

    log_avvio = LogTaskExport.objects.create(
        tipo=LogTaskExport.Tipo.PDF_MASSIVO,
        stato=LogTaskExport.Stato.OK,
        messaggio=f"Avviata generazione massiva: {totale} diari",
        edizione_pk=edizione_pk, edizione_str=edizione_str,
        utente_pk=utente_pk, utente_str=utente_str,
    )

    if utente and utente.email:
        _mail(
            f"[Plancia] Generazione massiva PDF avviata — {edizione_str}",
            f"Ciao {utente.first_name or utente.email},\n\n"
            f"Avviata la generazione di {totale} PDF per l'edizione {edizione_str}.\n"
            f"Riceverai aggiornamenti ogni 10 diari completati.",
            [utente.email],
        )

    completati: list[str] = []
    errori: list[str] = []

    try:
        for i, diario in enumerate(diari, 1):
            try:
                from apps.storage_drive.models import DriveFile, TipoFile
                # Salta se cache già presente
                if DriveFile.objects.filter(diario=diario, tipo=TipoFile.PDF).exists():
                    link = f"{base_url}/diari/{diario.pk}/pdf/"
                    completati.append(f"• {diario.squadriglia} (cached): {link}")
                    continue

                genera_pdf_diario(diario, include_relazione=True)

                if edizione.drive_oauth_account:
                    from apps.storage_drive.service import carica_pdf_diario
                    carica_pdf_diario(diario)

                link = f"{base_url}/diari/{diario.pk}/pdf/"
                completati.append(f"• {diario.squadriglia}: {link}")
                LogTaskExport.objects.create(
                    tipo=LogTaskExport.Tipo.PDF, stato=LogTaskExport.Stato.OK,
                    messaggio="PDF generato (massivo)",
                    diario_pk=diario.pk, diario_str=str(diario.squadriglia),
                    edizione_pk=edizione_pk, edizione_str=edizione_str,
                    utente_pk=utente_pk, utente_str=utente_str,
                )

            except Exception as exc:
                tb = tb_module.format_exc()
                errori.append(f"• {diario.squadriglia}: {exc}")
                LogTaskExport.objects.create(
                    tipo=LogTaskExport.Tipo.PDF, stato=LogTaskExport.Stato.ERRORE,
                    messaggio=str(exc), traceback_testo=tb,
                    diario_pk=diario.pk, diario_str=str(diario.squadriglia),
                    edizione_pk=edizione_pk, edizione_str=edizione_str,
                    utente_pk=utente_pk, utente_str=utente_str,
                )

            self.update_state(state="PROGRESS", meta={
                "progresso": i * 100 // totale,
                "completati": i,
                "totale": totale,
            })

            # Email di progresso ogni 10
            if i % 10 == 0 and utente and utente.email:
                _mail(
                    f"[Plancia] Progresso PDF — {i}/{totale} — {edizione_str}",
                    f"Completati {i}/{totale} diari.\n\nPDF disponibili:\n"
                    + "\n".join(completati[-10:]),
                    [utente.email],
                )

    finally:
        cache.delete(lock_key)

    # Email finale
    riepilogo = (
        f"Generazione massiva completata per {edizione_str}.\n"
        f"Completati: {len(completati)} / {totale}\n"
        f"Errori: {len(errori)}\n\n"
    )
    if completati:
        riepilogo += "PDF generati:\n" + "\n".join(completati) + "\n\n"
    if errori:
        riepilogo += "Errori:\n" + "\n".join(errori)

    if utente and utente.email:
        _mail(
            f"[Plancia] PDF massivi pronti — {edizione_str}",
            riepilogo,
            [utente.email],
        )

    # Notifica admin in caso di errori
    if errori:
        admin_emails = list(
            User.objects.filter(ruolo=Ruolo.ADMIN).exclude(email="").values_list("email", flat=True)
        )
        if admin_emails:
            _mail(
                f"[Plancia] Errori generazione massiva PDF — {edizione_str}",
                riepilogo + f"\n\nLog: {base_url}/impostazioni/log-export/",
                admin_emails,
            )

    LogTaskExport.objects.filter(pk=log_avvio.pk).update(
        messaggio=f"Completata: {len(completati)} ok, {len(errori)} errori su {totale} diari",
    )

    return {"ok": True, "totale": totale, "completati": len(completati), "errori": len(errori)}
