"""Schemi dell'helpdesk (ticket e risposte).

Ai router si passano i modelli: i campi calcolati usano i resolver di ninja.
"""
from __future__ import annotations

from datetime import datetime

from ninja import Schema


class UtenteTicketSchema(Schema):
    id: int
    nome: str
    email: str

    @staticmethod
    def resolve_nome(obj) -> str:
        return obj.get_full_name() or obj.email


class DiarioBreveSchema(Schema):
    id: int
    squadriglia: str
    edizione_anno: int

    @staticmethod
    def resolve_squadriglia(obj) -> str:
        return obj.squadriglia.nome

    @staticmethod
    def resolve_edizione_anno(obj) -> int:
        return obj.edizione.anno


class TicketSchema(Schema):
    id: int
    oggetto: str
    categoria: str
    categoria_display: str
    stato: str
    stato_display: str
    aperto_da: UtenteTicketSchema
    assegnato_a: UtenteTicketSchema | None
    diario: DiarioBreveSchema | None
    creato_at: datetime
    aggiornato_at: datetime
    chiuso_at: datetime | None

    @staticmethod
    def resolve_categoria_display(obj) -> str:
        return obj.get_categoria_display()

    @staticmethod
    def resolve_stato_display(obj) -> str:
        return obj.get_stato_display()


class RispostaSchema(Schema):
    id: int
    autore: UtenteTicketSchema
    testo: str
    creata_at: datetime


class AzioniTicketSchema(Schema):
    """Cosa può fare l'utente corrente sul ticket (per mostrare i pulsanti)."""

    rispondi: bool
    prendi_in_carico: bool
    chiudi: bool


class TicketDettaglioSchema(TicketSchema):
    corpo: str
    risposte: list[RispostaSchema]
    azioni: AzioniTicketSchema

    @staticmethod
    def resolve_risposte(obj) -> list:
        return list(obj.risposte.select_related("autore"))

    @staticmethod
    def resolve_azioni(obj, context) -> dict:
        from apps.helpdesk.models import StatoTicket
        from apps.helpdesk.services import e_staff_helpdesk

        user = context["request"].auth
        staff = e_staff_helpdesk(user)
        aperto = obj.stato != StatoTicket.CHIUSO
        return {
            "rispondi": aperto,
            "prendi_in_carico": staff and obj.stato == StatoTicket.APERTO,
            "chiudi": aperto,
        }


class TicketIn(Schema):
    oggetto: str
    corpo: str
    categoria: str
    diario_id: int | None = None


class RispostaIn(Schema):
    testo: str


class SceltaHelpdeskSchema(Schema):
    chiave: str
    etichetta: str


class OpzioniTicketSchema(Schema):
    """Valori per il form di apertura: categorie, stati e diari collegabili."""

    categorie: list[SceltaHelpdeskSchema]
    stati: list[SceltaHelpdeskSchema]
    diari: list[DiarioBreveSchema]
    staff: bool
