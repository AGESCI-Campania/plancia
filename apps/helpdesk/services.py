"""Regole dell'helpdesk: chi vede quali ticket e chi può fare cosa. Vedi docs sez. 13.

Usate dal router API `apps/api/routers/helpdesk.py`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet

from apps.accounts.models import Ruolo
from apps.helpdesk.models import CategoriaTicket, RispostaTicket, StatoTicket, Ticket

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.diaries.models import Diario

STAFF_HELPDESK = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)


def e_staff_helpdesk(user: User) -> bool:
    """Admin, Segreteria e Incaricati EG gestiscono tutti i ticket."""
    return user.ruolo in STAFF_HELPDESK or user.is_superuser


def ticket_visibili(user: User) -> QuerySet[Ticket]:
    """Lo staff vede tutti i ticket, gli altri solo quelli che hanno aperto."""
    qs = Ticket.objects.select_related("aperto_da", "assegnato_a", "diario")
    if not e_staff_helpdesk(user):
        qs = qs.filter(aperto_da=user)
    return qs


def controlla_accesso(user: User, ticket: Ticket) -> None:
    """403 se l'utente non è chi ha aperto il ticket né staff."""
    if ticket.aperto_da_id != user.pk and not e_staff_helpdesk(user):
        raise PermissionDenied("Non puoi accedere a questo ticket.")


def _richiedi_non_chiuso(ticket: Ticket) -> None:
    if ticket.stato == StatoTicket.CHIUSO:
        raise ValidationError({"__all__": ["Il ticket è chiuso."]})


def diari_selezionabili(user: User) -> QuerySet[Diario]:
    """Diari a cui si può collegare un nuovo ticket: i propri (Capo Squadriglia) o
    quelli di cui si è Capo Reparto (stessa regola di `diari_visibili`); nessuno per gli altri."""
    from apps.diaries.models import Diario

    socio = getattr(user, "socio", None)
    if user.ruolo == Ruolo.CSQ and socio:
        return Diario.objects.filter(csq=socio)
    if user.ruolo == Ruolo.CRP and socio:
        return Diario.objects.filter(crp=socio)
    return Diario.objects.none()


def apri_ticket(
    user: User, *, oggetto: str, corpo: str, categoria: str, diario_id: int | None = None
) -> Ticket:
    """Crea un ticket aperto da `user`; il diario, se indicato, deve essere tra i selezionabili."""
    errori: dict[str, list[str]] = {}
    oggetto = (oggetto or "").strip()
    corpo = (corpo or "").strip()
    if not oggetto:
        errori["oggetto"] = ["Questo campo è obbligatorio."]
    elif len(oggetto) > 200:
        errori["oggetto"] = ["Al massimo 200 caratteri."]
    if not corpo:
        errori["corpo"] = ["Questo campo è obbligatorio."]
    if categoria not in CategoriaTicket.values:
        errori["categoria"] = ["Categoria non valida."]
    diario = None
    if diario_id:
        diario = diari_selezionabili(user).filter(pk=diario_id).first()
        if diario is None:
            errori["diario"] = ["Diario non valido."]
    if errori:
        raise ValidationError(errori)
    return Ticket.objects.create(
        aperto_da=user, oggetto=oggetto, corpo=corpo, categoria=categoria, diario=diario
    )


def rispondi(user: User, ticket: Ticket, testo: str) -> RispostaTicket:
    """Aggiunge una risposta; se a rispondere è lo staff su un ticket aperto, lo prende in carico."""
    controlla_accesso(user, ticket)
    _richiedi_non_chiuso(ticket)
    testo = (testo or "").strip()
    if not testo:
        raise ValidationError({"testo": ["La risposta non può essere vuota."]})
    risposta = RispostaTicket.objects.create(ticket=ticket, autore=user, testo=testo)
    if ticket.stato == StatoTicket.APERTO and user.ruolo in STAFF_HELPDESK:
        ticket.prendi_in_carico(user)
    return risposta


def prendi_in_carico(user: User, ticket: Ticket) -> None:
    if not e_staff_helpdesk(user):
        raise PermissionDenied("Solo la gestione della piattaforma prende in carico i ticket.")
    _richiedi_non_chiuso(ticket)
    ticket.prendi_in_carico(user)


def chiudi(user: User, ticket: Ticket) -> None:
    """Chiude il ticket: chi l'ha aperto o lo staff."""
    controlla_accesso(user, ticket)
    _richiedi_non_chiuso(ticket)
    ticket.chiudi(user)
