"""Schemi dei dati pubblici del sito (`GET /sito`)."""
from __future__ import annotations

from datetime import datetime

from ninja import Schema


class SitoFooterLinkSchema(Schema):
    tipo: str
    url: str
    etichetta: str


class SitoFooterSchema(Schema):
    testo: str  # HTML già reso (footer_testo come template Django)
    links: list[SitoFooterLinkSchema]
    manuale_url: str


class PaginaBreveSchema(Schema):
    slug: str
    titolo: str


class PaginaSchema(PaginaBreveSchema):
    contenuto: str  # HTML
    aggiornato_at: datetime | None


class SitoManutenzioneSchema(Schema):
    attiva: bool
    messaggio: str


class ProviderLoginSchema(Schema):
    id: str
    nome: str


class LoginSchema(Schema):
    locale: bool
    provider: list[ProviderLoginSchema]


class SitoSchema(Schema):
    titolo: str
    sottotitolo: str
    versione: str
    commit: str
    footer: SitoFooterSchema
    pagine: list[PaginaBreveSchema]
    manutenzione: SitoManutenzioneSchema
    login: LoginSchema
