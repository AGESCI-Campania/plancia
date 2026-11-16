"""Schemi dei dati pubblici del sito (`GET /sito`)."""
from __future__ import annotations

from datetime import datetime

from ninja import Schema


class FooterLinkSchema(Schema):
    tipo: str
    url: str
    etichetta: str


class FooterSchema(Schema):
    testo: str  # HTML già reso (footer_testo come template Django)
    links: list[FooterLinkSchema]
    manuale_url: str


class PaginaBreveSchema(Schema):
    slug: str
    titolo: str


class PaginaSchema(PaginaBreveSchema):
    contenuto: str  # HTML
    aggiornato_at: datetime | None


class ManutenzioneSchema(Schema):
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
    footer: FooterSchema
    pagine: list[PaginaBreveSchema]
    manutenzione: ManutenzioneSchema
    login: LoginSchema
