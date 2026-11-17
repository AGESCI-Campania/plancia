# apps/api/schemas/impostazioni.py
"""Schemi del router `impostazioni`.

I campi segreti (password SMTP, API key e webhook secret del provider) non sono mai
restituiti: le letture espongono `<campo>_impostato: bool`; in scrittura un valore vuoto
o assente lascia invariato quello salvato.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from ninja import Schema

# --- Sezioni (lettura) ------------------------------------------------------


class IdentitaSchema(Schema):
    titolo: str
    sottotitolo: str


class FooterLinkImpostazioniSchema(Schema):
    id: int
    tipo: str
    tipo_display: str
    url: str
    etichetta: str
    ordine: int


class FooterImpostazioniSchema(Schema):
    footer_testo: str
    links: list[FooterLinkImpostazioniSchema]


class GmailOAuthSchema(Schema):
    attivo: bool
    account: str


class EmailSchema(Schema):
    email_mode: str
    from_name: str
    from_email: str
    email_backend_standard: str
    email_backend_massivo: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password_impostato: bool
    smtp_use_tls: bool
    email_provider: str
    email_provider_api_key_impostato: bool
    email_provider_webhook_secret_impostato: bool
    gmail_oauth: GmailOAuthSchema
    webhook_url: str


class SicurezzaSchema(Schema):
    mfa_obbligatoria_ruoli_estesi: bool
    axes_failure_limit: int
    axes_cooloff_minutes: int
    axes_use_attempt_expiration: bool


class AllegatiSchema(Schema):
    allegati_max_px: int


class DiagnosticaSchema(Schema):
    manutenzione: bool
    manutenzione_messaggio: str  # vuoto = messaggio predefinito
    debug_toolbar: bool
    debug_diagnostico: bool


class ScelteSchema(Schema):
    valore: str
    etichetta: str


class ImpostazioniSchema(Schema):
    identita: IdentitaSchema
    footer: FooterImpostazioniSchema
    email: EmailSchema
    sicurezza: SicurezzaSchema
    allegati: AllegatiSchema
    diagnostica: DiagnosticaSchema
    aggiornato_at: datetime | None
    scelte: dict[str, list[ScelteSchema]]  # opzioni per i campi a scelta (email_mode, …)


# --- Sezioni (scrittura parziale: i campi assenti restano invariati) ---------


class IdentitaIn(Schema):
    titolo: str | None = None
    sottotitolo: str | None = None


class FooterIn(Schema):
    footer_testo: str | None = None


class EmailIn(Schema):
    email_mode: str | None = None
    from_name: str | None = None
    from_email: str | None = None
    email_backend_standard: str | None = None
    email_backend_massivo: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None  # vuoto/assente = invariata
    smtp_use_tls: bool | None = None
    email_provider: str | None = None
    email_provider_api_key: str | None = None  # vuoto/assente = invariata
    email_provider_webhook_secret: str | None = None  # vuoto/assente = invariato


class SicurezzaIn(Schema):
    mfa_obbligatoria_ruoli_estesi: bool | None = None
    axes_failure_limit: int | None = None
    axes_cooloff_minutes: int | None = None
    axes_use_attempt_expiration: bool | None = None


class AllegatiIn(Schema):
    allegati_max_px: int | None = None


class DiagnosticaIn(Schema):
    manutenzione: bool | None = None
    manutenzione_messaggio: str | None = None  # "" = torna il messaggio predefinito
    debug_toolbar: bool | None = None
    debug_diagnostico: bool | None = None


class ManutenzioneImpostazioniSchema(Schema):
    manutenzione: bool
    messaggio: str  # vuoto = messaggio predefinito


class ManutenzioneIn(Schema):
    attiva: bool
    messaggio: str | None = None  # assente = invariato


# --- Footer link ------------------------------------------------------------


class FooterLinkIn(Schema):
    tipo: str = ""
    url: str = ""
    etichetta: str = ""


class FooterLinkPatch(Schema):
    tipo: str | None = None
    url: str | None = None
    etichetta: str | None = None


class OrdinaLinkIn(Schema):
    ids: list[int]


# --- Pagine statiche --------------------------------------------------------


class PaginaStaticaSchema(Schema):
    slug: str
    slug_display: str
    titolo: str
    contenuto: str
    aggiornato_at: datetime | None


class PaginaStaticaIn(Schema):
    titolo: str
    contenuto: str = ""


# --- Template email ---------------------------------------------------------


class MailTemplateRigaSchema(Schema):
    chiave: str
    tag_disponibili: list[str]
    esiste: bool
    oggetto: str | None
    attivo: bool | None
    aggiornato_at: datetime | None


class MailTemplateSchema(MailTemplateRigaSchema):
    corpo_html: str | None
    chiavi_senza_record: list[str]  # destinazioni possibili per "copia"


class MailTemplateIn(Schema):
    oggetto: str
    corpo_html: str
    attivo: bool = True


class CopiaTemplateIn(Schema):
    target_chiave: str


class UrlSchema(Schema):
    url: str


# --- Email di test, OAuth ---------------------------------------------------


class TestEmailIn(Schema):
    backend: Literal["smtp", "transazionale"] = "smtp"


class EsitoImpostazioniSchema(Schema):
    detail: str


# --- Log export, cache PDF, task --------------------------------------------


class LogExportSchema(Schema):
    id: int
    tipo: str
    tipo_display: str
    stato: str
    stato_display: str
    messaggio: str
    traceback_testo: str
    diario_id: int | None
    diario: str
    edizione_id: int | None
    edizione: str
    utente_id: int | None
    utente: str
    creato_at: datetime


class EdizioneCachePdfSchema(Schema):
    id: int
    anno: int
    nome: str
    pdf_in_cache: int
    generazione_in_corso: bool
    task_id: str | None


class FilePdfSchema(Schema):
    id: int
    nome: str
    diario_id: int | None
    squadriglia: str | None
    edizione_id: int | None
    dimensione: int
    url_esterno: str
    caricato_at: datetime


class EdizioneIdIn(Schema):
    edizione_id: int


class InvalidaCacheIn(Schema):
    edizione_id: int | None = None  # None = tutte le edizioni


class ConteggioSchema(Schema):
    detail: str
    eliminati: int


class ProgressoTaskSchema(Schema):
    stato: str
    progresso: int
    completati: int | None = None
    totale: int | None = None


# --- Axes -------------------------------------------------------------------


class AccessoBloccatoSchema(Schema):
    id: int
    ip_address: str | None
    username: str | None
    failures_since_start: int
    attempt_time: datetime
