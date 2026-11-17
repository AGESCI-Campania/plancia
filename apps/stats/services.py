"""Calcolo delle statistiche di chiusura per zona: esiti, tempi, ticket. Vedi docs sez. 13.

Usato dalla dashboard web (`apps/stats/views.py`) e dal router API `/statistiche`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.diaries.models import StatoDiario
from apps.evaluations.models import EsitoValutazione
from apps.helpdesk.models import StatoTicket

if TYPE_CHECKING:
    from apps.editions.models import Edizione


def edizione_di_riferimento(edizione_pk=None) -> Edizione | None:
    """L'edizione richiesta, altrimenti la più recente aperta/in valutazione, altrimenti l'ultima."""
    from apps.editions.models import Edizione, StatoEdizione

    edizioni = Edizione.objects.order_by("-anno")
    edizione = None
    if edizione_pk:
        try:
            edizione = edizioni.filter(pk=int(edizione_pk)).first()
        except (TypeError, ValueError):
            edizione = None
    if not edizione:
        edizione = edizioni.filter(
            stato__in=[StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE]
        ).first() or edizioni.first()
    return edizione


def stats_per_zona(edizione: Edizione) -> list[dict[str, Any]]:
    """Per ogni zona con diari nell'edizione: totale ed esiti pubblicati."""
    from apps.diaries.models import Diario
    from apps.org.models import Zona

    risultati = []
    for zona in Zona.objects.order_by("nome"):
        diari = Diario.objects.filter(edizione=edizione, squadriglia__reparto__gruppo__zona=zona)
        totale = diari.count()
        if not totale:
            continue
        approvati = diari.filter(
            valutazione__esito=EsitoValutazione.APPROVATA, pubblicato_at__isnull=False
        ).count()
        non_approvati = diari.filter(
            valutazione__esito=EsitoValutazione.NON_APPROVATA, pubblicato_at__isnull=False
        ).count()
        risultati.append({
            "zona": zona,
            "totale": totale,
            "approvati": approvati,
            "non_approvati": non_approvati,
            "maggiori_info": diari.filter(stato=StatoDiario.MAGGIORI_INFO).count(),
            "pubblicati": diari.filter(pubblicato_at__isnull=False).count(),
            "percentuale_approvati": round(approvati / totale * 100) if totale else 0,
        })
    return risultati


def stats_globali(edizione: Edizione) -> dict[str, int]:
    from apps.diaries.models import Diario

    diari = Diario.objects.filter(edizione=edizione)
    return {
        "totale": diari.count(),
        "inviati": diari.filter(
            stato__in=[
                StatoDiario.INVIATO, StatoDiario.IN_VALUTAZIONE,
                StatoDiario.IN_REVISIONE, StatoDiario.APPROVATO,
                StatoDiario.NON_APPROVATO,
            ]
        ).count(),
        "approvati": diari.filter(
            valutazione__esito=EsitoValutazione.APPROVATA, pubblicato_at__isnull=False
        ).count(),
        "non_approvati": diari.filter(
            valutazione__esito=EsitoValutazione.NON_APPROVATA, pubblicato_at__isnull=False
        ).count(),
        "in_compilazione": diari.filter(stato=StatoDiario.IN_COMPILAZIONE).count(),
        "pubblicati": diari.filter(pubblicato_at__isnull=False).count(),
    }


def stats_ticket(edizione: Edizione) -> dict[str, Any]:
    """Ticket collegati a diari dell'edizione, per stato e per categoria."""
    from apps.helpdesk.models import CategoriaTicket, Ticket

    tickets = Ticket.objects.filter(diario__edizione=edizione)
    return {
        "totale": tickets.count(),
        "aperti": tickets.filter(stato=StatoTicket.APERTO).count(),
        "chiusi": tickets.filter(stato=StatoTicket.CHIUSO).count(),
        "per_categoria": [
            {"chiave": val, "categoria": label, "count": tickets.filter(categoria=val).count()}
            for val, label in CategoriaTicket.choices
        ],
    }
