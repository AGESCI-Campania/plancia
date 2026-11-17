"""Helpdesk: ticket e risposte.

Ogni utente autenticato apre ticket e vede i propri; Admin, Segreteria e Incaricati EG
vedono e gestiscono tutti i ticket. Regole in `apps.helpdesk.services`.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import Router, Status
from ninja.pagination import LimitOffsetPagination, paginate

from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.schemas.helpdesk import (
    OpzioniTicketSchema,
    RispostaIn,
    RispostaSchema,
    TicketDettaglioSchema,
    TicketIn,
    TicketSchema,
)
from apps.helpdesk import services
from apps.helpdesk.models import CategoriaTicket, StatoTicket, Ticket

router = Router(tags=["helpdesk"])

_ERRORI = {401: ErroreSchema, 403: ErroreSchema, 404: ErroreSchema, 422: ErroreValidazioneSchema}
_RELAZIONI = ("aperto_da", "assegnato_a", "diario__squadriglia", "diario__edizione")


def _ticket(request, ticket_id: int) -> Ticket:
    """Il ticket, se l'utente può vederlo (404 se non esiste, 403 se è di altri)."""
    ticket = get_object_or_404(Ticket.objects.select_related(*_RELAZIONI), pk=ticket_id)
    services.controlla_accesso(request.auth, ticket)
    return ticket


@router.get("/opzioni", response={200: OpzioniTicketSchema, **_ERRORI},
            summary="Categorie, stati e diari collegabili a un nuovo ticket")
def opzioni(request):
    user = request.auth
    return {
        "categorie": [{"chiave": k, "etichetta": v} for k, v in CategoriaTicket.choices],
        "stati": [{"chiave": k, "etichetta": v} for k, v in StatoTicket.choices],
        "diari": services.diari_selezionabili(user).select_related("squadriglia", "edizione"),
        "staff": services.e_staff_helpdesk(user),
    }


@router.get("", response={200: list[TicketSchema], **_ERRORI},
            summary="Ticket visibili (propri; tutti per lo staff)")
@paginate(LimitOffsetPagination)
def lista(request, stato: str | None = None):
    qs = services.ticket_visibili(request.auth).select_related(*_RELAZIONI)
    if stato in StatoTicket.values:
        qs = qs.filter(stato=stato)
    return qs


@router.post("", response={201: TicketDettaglioSchema, **_ERRORI}, summary="Apri un ticket")
def crea(request, dati: TicketIn):
    ticket = services.apri_ticket(
        request.auth, oggetto=dati.oggetto, corpo=dati.corpo, categoria=dati.categoria,
        diario_id=dati.diario_id,
    )
    return Status(201, _ticket(request, ticket.pk))


@router.get("/{ticket_id}", response={200: TicketDettaglioSchema, **_ERRORI},
            summary="Dettaglio del ticket con le risposte")
def dettaglio(request, ticket_id: int):
    return _ticket(request, ticket_id)


@router.post("/{ticket_id}/risposte", response={201: RispostaSchema, **_ERRORI},
             summary="Rispondi al ticket")
def rispondi(request, ticket_id: int, dati: RispostaIn):
    """Se risponde lo staff a un ticket aperto, il ticket passa in lavorazione."""
    ticket = _ticket(request, ticket_id)
    return Status(201, services.rispondi(request.auth, ticket, dati.testo))


@router.post("/{ticket_id}/prendi-in-carico", response={200: TicketDettaglioSchema, **_ERRORI},
             summary="Prendi in carico il ticket (solo staff)")
def prendi_in_carico(request, ticket_id: int):
    ticket = _ticket(request, ticket_id)
    services.prendi_in_carico(request.auth, ticket)
    return _ticket(request, ticket_id)


@router.post("/{ticket_id}/chiudi", response={200: TicketDettaglioSchema, **_ERRORI},
             summary="Chiudi il ticket (chi l'ha aperto o lo staff)")
def chiudi(request, ticket_id: int):
    ticket = _ticket(request, ticket_id)
    services.chiudi(request.auth, ticket)
    return _ticket(request, ticket_id)
