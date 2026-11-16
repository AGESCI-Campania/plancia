# apps/api/routers/impostazioni.py
"""Impostazioni di piattaforma: sezioni del form, footer, pagine statiche, template email,
email di test, Gmail SMTP OAuth, log export, cache PDF, progresso task, axes, manutenzione.

Permessi come le viste web: Admin, Segreteria e Incaricati EG; eliminazione dei template
email e sblocco IP solo Admin. Lettura delle pagine statiche pubblica.
La logica sta in `apps.siteconfig.services` (condivisa con le viste web).
"""

from typing import Any

from django.shortcuts import get_object_or_404
from ninja import File, Query, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.pagination import LimitOffsetPagination, paginate
from ninja.responses import Status

from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.permissions import richiedi_admin, richiedi_staff
from apps.api.schemas.impostazioni import (
    AccessoBloccatoSchema,
    AllegatiIn,
    ConteggioSchema,
    CopiaTemplateIn,
    DiagnosticaIn,
    EdizioneCachePdfSchema,
    EdizioneIdIn,
    EmailIn,
    EsitoImpostazioniSchema,
    FilePdfSchema,
    FooterIn,
    FooterLinkImpostazioniSchema,
    FooterLinkIn,
    FooterLinkPatch,
    IdentitaIn,
    ImpostazioniSchema,
    InvalidaCacheIn,
    LogExportSchema,
    MailTemplateIn,
    MailTemplateRigaSchema,
    MailTemplateSchema,
    ManutenzioneImpostazioniSchema,
    ManutenzioneIn,
    OrdinaLinkIn,
    PaginaStaticaIn,
    PaginaStaticaSchema,
    ProgressoTaskSchema,
    SicurezzaIn,
    TestEmailIn,
    UrlSchema,
)

router = Router(tags=["impostazioni"])

_ERRORI = {401: ErroreSchema, 403: ErroreSchema, 404: ErroreSchema, 422: ErroreValidazioneSchema}


# ---------------------------------------------------------------------------
# Lettura e scrittura per sezioni
# ---------------------------------------------------------------------------

def _scelte(choices) -> list[dict[str, str]]:
    return [{"valore": v, "etichetta": str(e)} for v, e in choices]


def _link(link) -> FooterLinkImpostazioniSchema:
    return FooterLinkImpostazioniSchema(
        id=link.pk, tipo=link.tipo, tipo_display=link.get_tipo_display(),
        url=link.url, etichetta=link.etichetta, ordine=link.ordine,
    )


def _impostazioni(request) -> ImpostazioniSchema:
    from apps.siteconfig.models import (
        BackendPosta,
        EmailMode,
        EmailProvider,
        Impostazioni,
        TipoLink,
    )

    imp = Impostazioni.objects.get_or_create(pk=1)[0]
    return ImpostazioniSchema(
        identita={"titolo": imp.titolo, "sottotitolo": imp.sottotitolo},
        footer={
            "footer_testo": imp.footer_testo,
            "links": [_link(link) for link in imp.footer_links.all()],
        },
        email={
            "email_mode": imp.email_mode,
            "from_name": imp.from_name,
            "from_email": imp.from_email,
            "email_backend_standard": imp.email_backend_standard,
            "email_backend_massivo": imp.email_backend_massivo,
            "smtp_host": imp.smtp_host,
            "smtp_port": imp.smtp_port,
            "smtp_user": imp.smtp_user,
            "smtp_password_impostato": bool(imp.smtp_password),
            "smtp_use_tls": imp.smtp_use_tls,
            "email_provider": imp.email_provider,
            "email_provider_api_key_impostato": bool(imp.email_provider_api_key),
            "email_provider_webhook_secret_impostato": bool(imp.email_provider_webhook_secret),
            "gmail_oauth": {"attivo": imp.smtp_use_gmail_oauth,
                            "account": imp.smtp_gmail_account},
            "webhook_url": request.build_absolute_uri("/anymail/webhook/"),
        },
        sicurezza={
            "mfa_obbligatoria_ruoli_estesi": imp.mfa_obbligatoria_ruoli_estesi,
            "axes_failure_limit": imp.axes_failure_limit,
            "axes_cooloff_minutes": imp.axes_cooloff_minutes,
            "axes_use_attempt_expiration": imp.axes_use_attempt_expiration,
        },
        allegati={"allegati_max_px": imp.allegati_max_px},
        diagnostica={
            "manutenzione": imp.manutenzione,
            "manutenzione_messaggio": imp.manutenzione_messaggio,
            "debug_toolbar": imp.debug_toolbar,
            "debug_diagnostico": imp.debug_diagnostico,
        },
        aggiornato_at=imp.aggiornato_at,
        scelte={
            "email_mode": _scelte(EmailMode.choices),
            "email_provider": _scelte(EmailProvider.choices),
            "email_backend": _scelte(BackendPosta.choices),
            "footer_link_tipo": _scelte(TipoLink.choices),
        },
    )


@router.get("", response={200: ImpostazioniSchema, **_ERRORI},
            summary="Tutte le sezioni delle impostazioni (segreti esclusi)")
def leggi_impostazioni(request):
    richiedi_staff(request.auth)
    return _impostazioni(request)


def _aggiorna(request, sezione: str, payload: Schema) -> ImpostazioniSchema:
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    services.aggiorna_sezione(sezione, payload.dict(exclude_unset=True))
    return _impostazioni(request)


@router.patch("/identita", response={200: ImpostazioniSchema, **_ERRORI},
              summary="Modifica la sezione Identità (titolo, sottotitolo)")
def aggiorna_identita(request, payload: IdentitaIn):
    return _aggiorna(request, "identita", payload)


@router.patch("/footer", response={200: ImpostazioniSchema, **_ERRORI},
              summary="Modifica il testo del footer")
def aggiorna_footer(request, payload: FooterIn):
    return _aggiorna(request, "footer", payload)


@router.patch("/email", response={200: ImpostazioniSchema, **_ERRORI},
              summary="Modifica la sezione Posta elettronica (segreti vuoti = invariati)")
def aggiorna_email(request, payload: EmailIn):
    return _aggiorna(request, "email", payload)


@router.patch("/sicurezza", response={200: ImpostazioniSchema, **_ERRORI},
              summary="Modifica la sezione Sicurezza (MFA, blocco tentativi)")
def aggiorna_sicurezza(request, payload: SicurezzaIn):
    return _aggiorna(request, "sicurezza", payload)


@router.patch("/allegati", response={200: ImpostazioniSchema, **_ERRORI},
              summary="Modifica la sezione Allegati")
def aggiorna_allegati(request, payload: AllegatiIn):
    return _aggiorna(request, "allegati", payload)


@router.patch("/diagnostica", response={200: ImpostazioniSchema, **_ERRORI},
              summary="Modifica la sezione Diagnostica (manutenzione, debug)")
def aggiorna_diagnostica(request, payload: DiagnosticaIn):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    dati = payload.dict(exclude_unset=True)
    # Il messaggio non è nel form della vista web (che altrimenti lo azzererebbe):
    # si salva a parte, come fa il comando `manutenzione`.
    messaggio = dati.pop("manutenzione_messaggio", None)
    imp = services.aggiorna_sezione("diagnostica", dati)
    if messaggio is not None:
        imp.manutenzione_messaggio = messaggio.strip()
        imp.save(update_fields=["manutenzione_messaggio", "aggiornato_at"])
    return _impostazioni(request)


@router.get("/manutenzione", response={200: ManutenzioneImpostazioniSchema, **_ERRORI},
            summary="Stato della modalità manutenzione")
def leggi_manutenzione(request):
    from apps.siteconfig.models import Impostazioni

    richiedi_staff(request.auth)
    imp = Impostazioni.objects.get_or_create(pk=1)[0]
    return {"manutenzione": imp.manutenzione, "messaggio": imp.manutenzione_messaggio}


@router.put("/manutenzione", response={200: ManutenzioneImpostazioniSchema, **_ERRORI},
            summary="Attiva o disattiva la modalità manutenzione")
def imposta_manutenzione(request, payload: ManutenzioneIn):
    from apps.siteconfig.manutenzione import imposta_manutenzione
    from apps.siteconfig.models import Impostazioni

    richiedi_staff(request.auth)
    messaggio = payload.messaggio.strip() if payload.messaggio is not None else None
    imposta_manutenzione(payload.attiva, messaggio)
    imp = Impostazioni.objects.get(pk=1)
    return {"manutenzione": imp.manutenzione, "messaggio": imp.manutenzione_messaggio}


# ---------------------------------------------------------------------------
# Footer link (max 4)
# ---------------------------------------------------------------------------

def _footer_link(link_id: int):
    from apps.siteconfig.models import FooterLink

    return get_object_or_404(FooterLink, pk=link_id, impostazioni_id=1)


@router.get("/footer/link", response={200: list[FooterLinkImpostazioniSchema], **_ERRORI},
            summary="Link del footer, in ordine")
def lista_footer_link(request):
    from apps.siteconfig.models import FooterLink

    richiedi_staff(request.auth)
    return [_link(link) for link in FooterLink.objects.filter(impostazioni_id=1)]


@router.post("/footer/link", response={201: FooterLinkImpostazioniSchema, **_ERRORI},
             summary="Aggiunge un link al footer (al massimo 4)")
def crea_footer_link(request, payload: FooterLinkIn):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    return Status(201, _link(services.crea_footer_link(payload.dict())))


@router.patch("/footer/link/{int:link_id}", response={200: FooterLinkImpostazioniSchema, **_ERRORI},
              summary="Modifica un link del footer")
def modifica_footer_link(request, link_id: int, payload: FooterLinkPatch):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    link = _footer_link(link_id)
    dati = {"tipo": link.tipo, "url": link.url, "etichetta": link.etichetta,
            **payload.dict(exclude_unset=True, exclude_none=True)}
    link = services.valida_footer_link(dati, instance=link)
    link.save()
    return _link(link)


@router.delete("/footer/link/{int:link_id}", response={204: None, **_ERRORI},
               summary="Elimina un link del footer")
def elimina_footer_link(request, link_id: int):
    richiedi_staff(request.auth)
    _footer_link(link_id).delete()
    return Status(204, None)


@router.post("/footer/link/ordina", response={200: list[FooterLinkImpostazioniSchema], **_ERRORI},
             summary="Riordina i link del footer (tutti gli id, nel nuovo ordine)")
def ordina_footer_link(request, payload: OrdinaLinkIn):
    from apps.siteconfig import services
    from apps.siteconfig.models import FooterLink

    richiedi_staff(request.auth)
    services.ordina_footer_link(payload.ids)
    return [_link(link) for link in FooterLink.objects.filter(impostazioni_id=1)]


# ---------------------------------------------------------------------------
# Pagine statiche
# ---------------------------------------------------------------------------

def _pagina(p) -> PaginaStaticaSchema:
    return PaginaStaticaSchema(
        slug=p.slug, slug_display=p.get_slug_display(), titolo=p.titolo,
        contenuto=p.contenuto, aggiornato_at=p.aggiornato_at,
    )


@router.get("/pagine", response={200: list[PaginaStaticaSchema], **_ERRORI},
            summary="Pagine statiche (privacy, termini) per la modifica")
def lista_pagine(request):
    from apps.siteconfig import services
    from apps.siteconfig.models import SlugPagina

    richiedi_staff(request.auth)
    return [_pagina(services.pagina_per_modifica(s.value)) for s in SlugPagina]


@router.get("/pagine/{slug}", auth=None, response={200: PaginaStaticaSchema, 404: ErroreSchema},
            summary="Pagina statica per slug (pubblica)")
def leggi_pagina(request, slug: str):
    from apps.siteconfig import services

    return _pagina(services.pagina_pubblica(slug))


@router.put("/pagine/{slug}", response={200: PaginaStaticaSchema, **_ERRORI},
            summary="Modifica titolo e contenuto di una pagina statica")
def modifica_pagina(request, slug: str, payload: PaginaStaticaIn):
    from django.core.exceptions import ValidationError

    from apps.siteconfig import services
    from apps.siteconfig.forms import PaginaStaticaForm

    richiedi_staff(request.auth)
    pagina = services.pagina_per_modifica(slug)
    form = PaginaStaticaForm(payload.dict(), instance=pagina)
    if not form.is_valid():
        raise ValidationError({k: list(v) for k, v in form.errors.items()})
    return _pagina(form.save())


@router.post("/pagine/{slug}/importa", response={200: PaginaStaticaSchema, **_ERRORI},
             summary="Carica il contenuto predefinito di una pagina statica")
def importa_pagina(request, slug: str):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    return _pagina(services.importa_pagina_predefinita(slug))


# ---------------------------------------------------------------------------
# Template email
# ---------------------------------------------------------------------------

def _riga_template(chiave: str, tpl) -> dict[str, Any]:
    from apps.notifications.models import TAG_REGISTRY

    return {
        "chiave": chiave,
        "tag_disponibili": TAG_REGISTRY.get(chiave, []),
        "esiste": tpl is not None,
        "oggetto": tpl.oggetto if tpl else None,
        "attivo": tpl.attivo if tpl else None,
        "aggiornato_at": tpl.aggiornato_at if tpl else None,
    }


def _dettaglio_template(chiave: str) -> MailTemplateSchema:
    from apps.notifications.models import MailTemplate
    from apps.siteconfig import services

    tpl = MailTemplate.objects.filter(chiave=chiave).first()
    return MailTemplateSchema(
        **_riga_template(chiave, tpl),
        corpo_html=tpl.corpo_html if tpl else None,
        chiavi_senza_record=services.chiavi_senza_record(esclusa=chiave),
    )


@router.get("/mail", response={200: list[MailTemplateRigaSchema], **_ERRORI},
            summary="Template email: tutte le chiavi, con o senza personalizzazione")
def lista_template(request):
    from apps.notifications.models import TAG_REGISTRY, MailTemplate

    richiedi_staff(request.auth)
    db = {t.chiave: t for t in MailTemplate.objects.all()}
    return [_riga_template(chiave, db.get(chiave)) for chiave in TAG_REGISTRY]


@router.post("/immagini-mail", response={201: UrlSchema, **_ERRORI},
             summary="Carica un'immagine per l'editor dei template email (max 2 MB)")
def carica_immagine_mail(request, file: UploadedFile = File(...)):  # noqa: B008
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    return Status(201, {"url": request.build_absolute_uri(services.salva_immagine_mail(file))})


@router.get("/mail/{chiave}", response={200: MailTemplateSchema, **_ERRORI},
            summary="Dettaglio di un template email (tag disponibili, corpo)")
def leggi_template(request, chiave: str):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    services.chiave_template_valida(chiave)
    return _dettaglio_template(chiave)


@router.put("/mail/{chiave}", response={200: MailTemplateSchema, **_ERRORI},
            summary="Crea o modifica un template email")
def salva_template(request, chiave: str, payload: MailTemplateIn):
    from django.core.exceptions import ValidationError

    from apps.notifications.models import MailTemplate
    from apps.siteconfig import services
    from apps.siteconfig.forms import MailTemplateForm

    richiedi_staff(request.auth)
    services.chiave_template_valida(chiave)
    form = MailTemplateForm(
        {**payload.dict(), "chiave": chiave},
        instance=MailTemplate.objects.filter(chiave=chiave).first(),
        chiave_fissa=chiave,
    )
    if not form.is_valid():
        raise ValidationError({k: list(v) for k, v in form.errors.items()})
    form.save()
    return _dettaglio_template(chiave)


@router.delete("/mail/{chiave}", response={204: None, **_ERRORI},
               summary="Elimina un template email (torna il file predefinito; solo Admin)")
def elimina_template(request, chiave: str):
    from apps.notifications.models import MailTemplate

    richiedi_admin(request.auth)
    get_object_or_404(MailTemplate, chiave=chiave).delete()
    return Status(204, None)


@router.post("/mail/{chiave}/importa", response={201: MailTemplateSchema, **_ERRORI},
             summary="Crea il template email dal file predefinito")
def importa_template(request, chiave: str):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    services.importa_mail_template(chiave)
    return Status(201, _dettaglio_template(chiave))


@router.post("/mail/{chiave}/copia", response={201: MailTemplateSchema, **_ERRORI},
             summary="Copia oggetto e corpo verso una chiave non ancora personalizzata")
def copia_template(request, chiave: str, payload: CopiaTemplateIn):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    nuovo = services.copia_mail_template(chiave, payload.target_chiave)
    return Status(201, _dettaglio_template(nuovo.chiave))


# ---------------------------------------------------------------------------
# Email di test e Gmail SMTP OAuth
# ---------------------------------------------------------------------------

@router.post("/email/test", response={200: EsitoImpostazioniSchema, **_ERRORI},
             summary="Invia un'email di test al proprio indirizzo (SMTP o provider)")
def test_email(request, payload: TestEmailIn):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    label = "provider transazionale" if payload.backend == "transazionale" else "SMTP"
    try:
        services.invia_email_test(payload.backend, request.auth.email)
    except Exception as exc:
        raise HttpError(422, f"Errore nell'invio ({label}): {exc}") from None
    return {"detail": f"Email di test ({label}) inviata a {request.auth.email}."}


@router.post("/email/gmail/oauth", response={200: UrlSchema, **_ERRORI},
             summary="Avvia il collegamento Gmail SMTP OAuth: restituisce l'URL di consenso")
def avvia_gmail_oauth(request):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    return {"url": services.url_autorizzazione_gmail(request.session, origine="spa")}


@router.post("/email/gmail/disconnetti", response={200: ImpostazioniSchema, **_ERRORI},
             summary="Scollega l'account Gmail OAuth")
def disconnetti_gmail(request):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    services.scollega_gmail()
    return _impostazioni(request)


# ---------------------------------------------------------------------------
# Log export
# ---------------------------------------------------------------------------

@router.get("/log-export", response={200: list[LogExportSchema], **_ERRORI},
            summary="Log di generazione PDF ed Excel (più recenti prima)")
@paginate(LimitOffsetPagination)
def log_export(request):
    from apps.exports.models import LogTaskExport

    richiedi_staff(request.auth)
    return [
        LogExportSchema(
            id=log.pk, tipo=log.tipo, tipo_display=log.get_tipo_display(),
            stato=log.stato, stato_display=log.get_stato_display(),
            messaggio=log.messaggio, traceback_testo=log.traceback_testo,
            diario_id=log.diario_pk, diario=log.diario_str,
            edizione_id=log.edizione_pk, edizione=log.edizione_str,
            utente_id=log.utente_pk, utente=log.utente_str, creato_at=log.creato_at,
        )
        for log in LogTaskExport.objects.all()
    ]


# ---------------------------------------------------------------------------
# Cache PDF e generazione massiva
# ---------------------------------------------------------------------------

@router.get("/cache-pdf", response={200: list[EdizioneCachePdfSchema], **_ERRORI},
            summary="Edizioni con PDF in cache e stato della generazione massiva")
def cache_pdf(request):
    from django.db.models import Count, Q

    from apps.editions.models import Edizione
    from apps.siteconfig import services
    from apps.storage_drive.models import TipoFile

    richiedi_staff(request.auth)
    edizioni = Edizione.objects.order_by("-anno").annotate(
        n_pdf=Count("diari__drive_files", filter=Q(diari__drive_files__tipo=TipoFile.PDF))
    )
    risultato = []
    for ed in edizioni:
        lock, task_id = services.stato_massivo(ed.pk)
        risultato.append(EdizioneCachePdfSchema(
            id=ed.pk, anno=ed.anno, nome=str(ed), pdf_in_cache=ed.n_pdf,
            generazione_in_corso=lock, task_id=task_id,
        ))
    return risultato


class FiltroFilePdf(Schema):
    edizione_id: int | None = None


@router.get("/cache-pdf/file", response={200: list[FilePdfSchema], **_ERRORI},
            summary="PDF in cache (filtro per edizione)")
@paginate(LimitOffsetPagination)
def file_pdf(request, filtri: Query[FiltroFilePdf]):
    from apps.storage_drive.models import DriveFile, TipoFile

    richiedi_staff(request.auth)
    qs = DriveFile.objects.filter(tipo=TipoFile.PDF).select_related(
        "diario__squadriglia"
    ).order_by("diario__edizione__anno", "diario__squadriglia__nome")
    if filtri.edizione_id is not None:
        qs = qs.filter(diario__edizione_id=filtri.edizione_id)
    return [
        FilePdfSchema(
            id=f.pk, nome=f.nome, diario_id=f.diario_id,
            squadriglia=f.diario.squadriglia.nome if f.diario else None,
            edizione_id=f.diario.edizione_id if f.diario else f.edizione_id,
            dimensione=f.dimensione, url_esterno=f.url_esterno, caricato_at=f.caricato_at,
        )
        for f in qs
    ]


@router.delete("/cache-pdf/file/{int:file_id}", response={204: None, **_ERRORI},
               summary="Elimina un PDF dalla cache")
def elimina_file_pdf(request, file_id: int):
    from apps.storage_drive.models import DriveFile, TipoFile

    richiedi_staff(request.auth)
    get_object_or_404(DriveFile, pk=file_id, tipo=TipoFile.PDF).delete()
    return Status(204, None)


@router.post("/cache-pdf/invalida", response={200: ConteggioSchema, **_ERRORI},
             summary="Svuota la cache PDF di un'edizione o di tutte")
def invalida_cache(request, payload: InvalidaCacheIn):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    n = services.invalida_cache_pdf(payload.edizione_id)
    return {"detail": f"Eliminati {n} PDF dalla cache.", "eliminati": n}


@router.post("/cache-pdf/genera", response={202: EsitoImpostazioniSchema, **_ERRORI},
             summary="Avvia la generazione massiva dei PDF di un'edizione")
def genera_massivo(request, payload: EdizioneIdIn):
    from apps.editions.models import Edizione
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    edizione = get_object_or_404(Edizione, pk=payload.edizione_id)
    services.avvia_pdf_massivo(edizione.pk, request.auth.pk)
    return Status(202, {"detail": (
        "Generazione massiva avviata. Riceverai una mail al termine. "
        "Durante la generazione i PDF singoli per questa edizione sono disabilitati."
    )})


@router.post("/cache-pdf/interrompi", response={202: EsitoImpostazioniSchema, **_ERRORI},
             summary="Chiede l'interruzione della generazione massiva")
def interrompi_massivo(request, payload: EdizioneIdIn):
    from apps.editions.models import Edizione
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    edizione = get_object_or_404(Edizione, pk=payload.edizione_id)
    services.interrompi_pdf_massivo(edizione.pk)
    return Status(202, {"detail": "Interruzione richiesta. Il task si fermerà dopo il diario in corso."})


@router.get("/task/{task_id}", response={200: ProgressoTaskSchema, **_ERRORI},
            summary="Avanzamento di un task asincrono (generazione massiva PDF)")
def progresso_task(request, task_id: str):
    from apps.siteconfig import services

    richiedi_staff(request.auth)
    return services.progresso_task(task_id)


# ---------------------------------------------------------------------------
# IP bloccati (django-axes)
# ---------------------------------------------------------------------------

@router.get("/axes", response={200: list[AccessoBloccatoSchema], **_ERRORI},
            summary="Tentativi di accesso falliti registrati (ultimi 100)")
def lista_accessi(request):
    from axes.models import AccessAttempt

    richiedi_staff(request.auth)
    return [
        AccessoBloccatoSchema(
            id=a.pk, ip_address=a.ip_address, username=a.username,
            failures_since_start=a.failures_since_start, attempt_time=a.attempt_time,
        )
        for a in AccessAttempt.objects.order_by("-attempt_time")[:100]
    ]


@router.delete("/axes/{int:attempt_id}", response={204: None, **_ERRORI},
               summary="Sblocca un IP (solo Admin)")
def sblocca_accesso(request, attempt_id: int):
    from apps.siteconfig import services

    richiedi_admin(request.auth)
    services.sblocca_accessi(attempt_id)
    return Status(204, None)


@router.post("/axes/sblocca-tutti", response={200: ConteggioSchema, **_ERRORI},
             summary="Sblocca tutti gli IP (solo Admin)")
def sblocca_tutti(request):
    from apps.siteconfig import services

    richiedi_admin(request.auth)
    n = services.sblocca_accessi()
    return {"detail": f"Sbloccati tutti i {n} IP bloccati.", "eliminati": n}
