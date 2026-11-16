"""Schemi della gestione utenti (`/utenti`)."""
from __future__ import annotations

from datetime import date

from ninja import Schema

from apps.api.schemas.me import (
    LoginEventSchema,
    NominaSchema,
    RuoloSchema,
    SocioBreveSchema,
)


class UtenteListaSchema(Schema):
    id: int
    email: str
    nome_completo: str
    ruolo: RuoloSchema
    is_active: bool
    socio: SocioBreveSchema | None = None


class UtenteDettaglioSchema(Schema):
    id: int
    email: str
    nome_completo: str
    first_name: str
    last_name: str
    ruolo: RuoloSchema
    ruoli_attivi: list[RuoloSchema]
    is_active: bool
    is_staff: bool
    is_superuser: bool
    socio: SocioBreveSchema | None = None
    nomine: list[NominaSchema]
    accessi: list[LoginEventSchema]
    ruoli_nominabili: list[RuoloSchema]
    puo_impersonare: bool


class OpzioniUtentiSchema(Schema):
    """Ruoli disponibili nei form della pagina Utenti per l'utente corrente."""

    ruoli: list[RuoloSchema]
    ruoli_nominabili: list[RuoloSchema]
    ruoli_nominabili_da_socio: list[RuoloSchema]
    ruoli_staff_creabili: list[RuoloSchema]
    puo_impersonare: bool


class NominaCreaSchema(Schema):
    ruolo: str
    edizione_id: int | None = None
    scadenza: date | None = None


class UtenteStaffCreaSchema(Schema):
    email: str
    first_name: str = ""
    last_name: str = ""
    ruolo: str


class UtenteDaSocioCreaSchema(Schema):
    socio_id: int
    ruolo: str


class UtenteCreatoSchema(Schema):
    utente: UtenteDettaglioSchema
    nomina: NominaSchema
    creato: bool
    detail: str
