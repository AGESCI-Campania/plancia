# apps/siteconfig/services.py
"""Logica delle Impostazioni condivisa da viste web e API (`apps/api/routers/impostazioni.py`).

Sezioni del form, pagine statiche, template email, email di test, Gmail SMTP OAuth (PKCE),
cache PDF e generazione massiva, sblocco IP (axes), progresso dei task Celery.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import uuid
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError

from apps.notifications.models import TAG_REGISTRY, MailTemplate
from apps.siteconfig.forms import CAMPI_SMTP_MANUALI, SEZIONE_FORM
from apps.siteconfig.models import Impostazioni, PaginaStatica, SlugPagina

if TYPE_CHECKING:
    from django import forms

# Campi segreti: mai restituiti in chiaro; un valore vuoto in scrittura li lascia invariati.
CAMPI_SEGRETI = ("smtp_password", "email_provider_api_key", "email_provider_webhook_secret")


# ---------------------------------------------------------------------------
# Sezioni del form Impostazioni
# ---------------------------------------------------------------------------

def _sorgente_template(nome: str) -> str:
    """Testo sorgente di un template su file (TemplateDoesNotExist se manca)."""
    from django.template.loader import get_template

    return get_template(nome).template.source  # type: ignore[attr-defined]  # backend Django


def salva_sezione(form: forms.ModelForm, sezione: str) -> Impostazioni:
    """Salva un form di sezione già validato aggiornando solo i suoi campi.

    Con Gmail OAuth attivo i campi SMTP manuali non si toccano (sono sostituiti da OAuth).
    """
    update_fields = list(SEZIONE_FORM[sezione]._meta.fields or [])
    if sezione == "email" and form.instance.smtp_use_gmail_oauth:
        update_fields = [f for f in update_fields if f not in CAMPI_SMTP_MANUALI]
    saved = form.save(commit=False)
    saved.save(update_fields=[*update_fields, "aggiornato_at"])
    cache.set(Impostazioni.CACHE_KEY, saved, 300)
    return saved


def aggiorna_sezione(sezione: str, dati: dict[str, Any]) -> Impostazioni:
    """Aggiornamento parziale di una sezione: i campi assenti restano invariati.

    Usa lo stesso form della vista web (stessi controlli); i segreti vuoti o assenti
    mantengono il valore salvato. ValidationError con gli errori per campo.
    """
    from django.forms.models import model_to_dict

    if sezione not in SEZIONE_FORM:
        raise ValidationError({"sezione": ["Sezione non valida."]})
    form_class = SEZIONE_FORM[sezione]
    imp = Impostazioni.objects.get_or_create(pk=1)[0]  # da DB, non dalla cache
    campi = list(form_class._meta.fields or [])
    correnti = model_to_dict(imp, fields=campi)
    nuovi = {k: v for k, v in dati.items() if k in campi and v is not None}
    for segreto in CAMPI_SEGRETI:
        if segreto in nuovi and nuovi[segreto] == "":
            del nuovi[segreto]
    form = form_class({**correnti, **nuovi}, instance=imp)
    if not form.is_valid():
        raise ValidationError({k: list(v) for k, v in form.errors.items()})
    return salva_sezione(form, sezione)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

MAX_FOOTER_LINK = 4


def valida_footer_link(dati: dict[str, Any], instance=None):
    """Valida un link del footer con FooterLinkForm; restituisce l'istanza non salvata."""
    from apps.siteconfig.forms import FooterLinkForm

    form = FooterLinkForm(dati, instance=instance)
    if not form.is_valid():
        raise ValidationError({k: list(v) for k, v in form.errors.items()})
    return form.save(commit=False)


def crea_footer_link(dati: dict[str, Any]):
    imp = Impostazioni.objects.get_or_create(pk=1)[0]
    if imp.footer_links.count() >= MAX_FOOTER_LINK:
        raise ValidationError(f"Al massimo {MAX_FOOTER_LINK} link nel footer.")
    link = valida_footer_link(dati)
    link.impostazioni = imp
    ultimo = imp.footer_links.order_by("-ordine").first()
    link.ordine = (ultimo.ordine + 1) if ultimo else 0
    link.save()
    return link


def ordina_footer_link(ids: list[int]) -> None:
    """Riordina i link del footer secondo `ids` (tutti e soli i link esistenti)."""
    from apps.siteconfig.models import FooterLink

    imp = Impostazioni.objects.get_or_create(pk=1)[0]
    esistenti = set(FooterLink.objects.filter(impostazioni=imp).values_list("pk", flat=True))
    if set(ids) != esistenti or len(ids) != len(esistenti):
        raise ValidationError({"ids": ["Indica tutti i link del footer, una volta ciascuno."]})
    for posizione, pk in enumerate(ids):
        FooterLink.objects.filter(pk=pk).update(ordine=posizione)


# ---------------------------------------------------------------------------
# Pagine statiche
# ---------------------------------------------------------------------------

def _slug_valido(slug: str) -> SlugPagina:
    from django.http import Http404

    try:
        return SlugPagina(slug)
    except ValueError:
        raise Http404 from None


def pagina_pubblica(slug: str) -> PaginaStatica:
    """Pagina per la lettura pubblica; se non esiste, una pagina vuota non salvata."""
    etichetta = _slug_valido(slug).label
    return PaginaStatica.objects.filter(slug=slug).first() or PaginaStatica(
        slug=slug, titolo=etichetta, contenuto="<p>Contenuto non ancora disponibile.</p>",
    )


def pagina_per_modifica(slug: str) -> PaginaStatica:
    etichetta = _slug_valido(slug).label
    return PaginaStatica.objects.get_or_create(
        slug=slug, defaults={"titolo": etichetta, "contenuto": ""},
    )[0]


def importa_pagina_predefinita(slug: str) -> PaginaStatica:
    """Carica il contenuto da templates/siteconfig/default_pages/<slug>.html."""
    from django.template import TemplateDoesNotExist

    _slug_valido(slug)
    try:
        contenuto = _sorgente_template(f"siteconfig/default_pages/{slug}.html")
    except TemplateDoesNotExist:
        raise ValidationError(f"Nessun template predefinito trovato per «{slug}».") from None
    pagina = pagina_per_modifica(slug)
    pagina.contenuto = contenuto
    pagina.save()
    return pagina


# ---------------------------------------------------------------------------
# Template email
# ---------------------------------------------------------------------------

def chiave_template_valida(chiave: str) -> str:
    from django.http import Http404

    if chiave not in TAG_REGISTRY:
        raise Http404("Chiave template non valida.")
    return chiave


def chiavi_senza_record(esclusa: str | None = None) -> list[str]:
    db_keys = set(MailTemplate.objects.values_list("chiave", flat=True))
    return [k for k in TAG_REGISTRY if k != esclusa and k not in db_keys]


def importa_mail_template(chiave: str) -> tuple[MailTemplate, bool]:
    """Crea il template dal file templates/mail/<chiave>.html.

    Restituisce (template, trovato_file): senza file il template nasce vuoto.
    """
    from django.template import TemplateDoesNotExist

    chiave_template_valida(chiave)
    if MailTemplate.objects.filter(chiave=chiave).exists():
        raise ValidationError(f"Il template «{chiave}» esiste già: modifica quello.")
    try:
        corpo, trovato = _sorgente_template(f"mail/{chiave}.html"), True
    except TemplateDoesNotExist:
        corpo, trovato = "", False
    tpl = MailTemplate.objects.create(
        chiave=chiave, oggetto=chiave.replace("_", " ").capitalize(),
        corpo_html=corpo, attivo=True,
    )
    return tpl, trovato


def copia_mail_template(chiave: str, target_chiave: str) -> MailTemplate:
    """Duplica oggetto e corpo verso una chiave che non ha ancora un record."""
    source = MailTemplate.objects.get(chiave=chiave)
    target_chiave = (target_chiave or "").strip()
    if target_chiave not in TAG_REGISTRY:
        raise ValidationError({"target_chiave": ["Chiave target non valida."]})
    if MailTemplate.objects.filter(chiave=target_chiave).exists():
        raise ValidationError({"target_chiave": [f"Il template «{target_chiave}» esiste già."]})
    return MailTemplate.objects.create(
        chiave=target_chiave, oggetto=source.oggetto,
        corpo_html=source.corpo_html, attivo=source.attivo,
    )


IMMAGINI_MAIL_TIPI = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
IMMAGINI_MAIL_MAX = 2 * 1024 * 1024  # 2 MB


def salva_immagine_mail(upload) -> str:
    """Salva un'immagine per l'editor dei template email; restituisce il percorso pubblico."""
    if not upload:
        raise ValidationError({"file": ["Nessun file ricevuto."]})
    if upload.content_type not in IMMAGINI_MAIL_TIPI:
        raise ValidationError({"file": ["Tipo non supportato. Usa JPEG, PNG, GIF o WebP."]})
    if upload.size > IMMAGINI_MAIL_MAX:
        raise ValidationError({"file": ["File troppo grande (max 2 MB)."]})

    ext = os.path.splitext(upload.name)[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    save_dir = os.path.join(settings.MEDIA_ROOT, "mail_images")
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, filename), "wb") as fh:
        for chunk in upload.chunks():
            fh.write(chunk)
    media_prefix = "/" + settings.MEDIA_URL.lstrip("/")
    return f"{media_prefix}mail_images/{filename}"


# ---------------------------------------------------------------------------
# Email di test
# ---------------------------------------------------------------------------

def invia_email_test(backend_tipo: str, destinatario: str) -> str:
    """Invia un'email di test via SMTP o provider transazionale; restituisce l'etichetta.

    Le eccezioni del backend si propagano al chiamante.
    """
    from django.core.mail import EmailMessage

    from apps.siteconfig.email_backends import _smtp_backend, _transazionale_backend

    imp = Impostazioni.get()
    if backend_tipo == "transazionale":
        conn, label = _transazionale_backend(imp, fail_silently=False), "provider transazionale"
    else:
        conn, label = _smtp_backend(imp, fail_silently=False), "SMTP"
    msg = EmailMessage(
        subject=f"Test invio email ({label}) — {imp.titolo or 'Plancia'}",
        body=(
            f"Questo è un messaggio di test inviato tramite {label} "
            "dalle impostazioni di Plancia.\n"
            "Se lo ricevi, la configurazione funziona correttamente."
        ),
        from_email=imp.from_email_completo,
        to=[destinatario],
    )
    conn.send_messages([msg])
    return label


# ---------------------------------------------------------------------------
# Gmail SMTP OAuth (PKCE)
# ---------------------------------------------------------------------------

GMAIL_SMTP_SCOPES = [
    "https://mail.google.com/",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]
SESSIONE_GMAIL_STATE = "gmail_smtp_oauth_state"
SESSIONE_GMAIL_VERIFIER = "gmail_smtp_oauth_code_verifier"


def _flow_gmail(state: str | None = None):
    from google_auth_oauthlib.flow import Flow

    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uris": [settings.GOOGLE_GMAIL_SMTP_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GMAIL_SMTP_SCOPES,
        state=state,
        redirect_uri=settings.GOOGLE_GMAIL_SMTP_REDIRECT_URI,
    )


def url_autorizzazione_gmail(session) -> str:
    """URL di consenso Google; salva state e code_verifier (PKCE) in sessione."""
    code_verifier = secrets.token_urlsafe(96)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    auth_url, state = _flow_gmail().authorization_url(
        access_type="offline",
        prompt="consent",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    session[SESSIONE_GMAIL_STATE] = state
    session[SESSIONE_GMAIL_VERIFIER] = code_verifier
    return auth_url


def completa_oauth_gmail(session, state_ricevuto: str | None, authorization_response: str) -> str:
    """Scambia il codice, salva GmailSMTPCredenziali e attiva Gmail OAuth; restituisce l'account.

    ValidationError se lo state non corrisponde; le eccezioni di Google si propagano.
    """
    from django.utils import timezone
    from googleapiclient.discovery import build

    from apps.siteconfig.models import GmailSMTPCredenziali

    state = session.pop(SESSIONE_GMAIL_STATE, None)
    code_verifier = session.pop(SESSIONE_GMAIL_VERIFIER, None)
    if not state or state != state_ricevuto:
        raise ValidationError("Sessione OAuth non valida. Riprova.")

    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
    flow = _flow_gmail(state=state)
    flow.fetch_token(authorization_response=authorization_response, code_verifier=code_verifier)
    creds = flow.credentials

    email = build("oauth2", "v2", credentials=creds).userinfo().get().execute().get("email", "")
    expires_at = None
    if creds.expiry:
        expires_at = (
            timezone.make_aware(creds.expiry) if creds.expiry.tzinfo is None else creds.expiry
        )
    GmailSMTPCredenziali.objects.update_or_create(
        account_email=email,
        defaults={
            "access_token": creds.token,
            "refresh_token": creds.refresh_token or "",
            "expires_at": expires_at,
        },
    )
    imp = Impostazioni.objects.get_or_create(pk=1)[0]
    imp.smtp_gmail_account = email
    imp.smtp_use_gmail_oauth = True
    imp.save(update_fields=["smtp_gmail_account", "smtp_use_gmail_oauth", "aggiornato_at"])
    return email


def scollega_gmail() -> None:
    """Elimina le credenziali dell'account collegato e disattiva Gmail OAuth."""
    from apps.siteconfig.models import GmailSMTPCredenziali

    imp = Impostazioni.objects.get_or_create(pk=1)[0]
    if imp.smtp_gmail_account:
        GmailSMTPCredenziali.objects.filter(account_email=imp.smtp_gmail_account).delete()
    imp.smtp_use_gmail_oauth = False
    imp.smtp_gmail_account = ""
    imp.save(update_fields=["smtp_use_gmail_oauth", "smtp_gmail_account", "aggiornato_at"])


# ---------------------------------------------------------------------------
# Cache PDF e generazione massiva
# ---------------------------------------------------------------------------

def chiave_task_massivo(edizione_pk: int) -> str:
    return f"pdf_massivo_task_id:{edizione_pk}"


def stato_massivo(edizione_pk: int) -> tuple[bool, str | None]:
    """(lock attivo, task_id) della generazione massiva di un'edizione."""
    from apps.exports.tasks import lock_key_massivo

    lock = bool(cache.get(lock_key_massivo(edizione_pk)))
    return lock, (cache.get(chiave_task_massivo(edizione_pk)) if lock else None)


def avvia_pdf_massivo(edizione_pk: int, utente_pk: int) -> None:
    """Prende il lock (atomico) e accoda la generazione massiva dei PDF dell'edizione."""
    from apps.exports.tasks import lock_key_massivo, task_genera_pdf_massivo

    if not cache.add(lock_key_massivo(edizione_pk), True, 7200):
        raise ValidationError("Generazione massiva già in corso per questa edizione.")
    task_genera_pdf_massivo.delay(edizione_pk, utente_pk)


def interrompi_pdf_massivo(edizione_pk: int) -> None:
    from apps.exports.tasks import cancel_key_massivo

    cache.set(cancel_key_massivo(edizione_pk), True, 3600)


def invalida_cache_pdf(edizione_pk: int | None = None) -> int:
    """Elimina i PDF in cache (di un'edizione o tutti); restituisce quanti."""
    from apps.storage_drive.models import DriveFile, TipoFile

    qs = DriveFile.objects.filter(tipo=TipoFile.PDF)
    if edizione_pk is not None:
        qs = qs.filter(diario__edizione_id=edizione_pk)
    count = qs.count()
    qs.delete()
    return count


# ---------------------------------------------------------------------------
# Task Celery e axes
# ---------------------------------------------------------------------------

def progresso_task(task_id: str) -> dict[str, Any]:
    """Stato e avanzamento di un task Celery dal result backend."""
    from celery.result import AsyncResult

    result = AsyncResult(task_id)
    state = result.state
    if state == "PROGRESS":
        meta = result.info or {}
        return {
            "stato": "PROGRESS",
            "progresso": meta.get("progresso", 0),
            "completati": meta.get("completati", 0),
            "totale": meta.get("totale", 0),
        }
    if state == "SUCCESS":
        return {"stato": "SUCCESS", "progresso": 100}
    # FAILURE, PENDING, STARTED, RETRY
    return {"stato": state, "progresso": 0}


def sblocca_accessi(attempt_pk: int | None = None) -> int:
    """Elimina un AccessAttempt di axes (o tutti se `attempt_pk` è None); restituisce quanti."""
    from axes.models import AccessAttempt

    if attempt_pk is None:
        count = AccessAttempt.objects.count()
        AccessAttempt.objects.all().delete()
        return count
    AccessAttempt.objects.get(pk=attempt_pk).delete()
    return 1
