"""Statistiche per zona (Admin, Segreteria, Incaricati EG). Calcoli in `apps.stats.services`."""
from __future__ import annotations

from ninja import Router

from apps.api.errors import ErroreSchema
from apps.api.permissions import richiedi_staff
from apps.api.schemas.statistiche import StatisticheSchema
from apps.stats import services

router = Router(tags=["statistiche"])


@router.get("", response={200: StatisticheSchema, 401: ErroreSchema, 403: ErroreSchema},
            summary="Dati della dashboard statistiche per zona")
def statistiche(request, edizione_id: int | None = None):
    """Senza `edizione_id` usa l'edizione aperta o in valutazione più recente (o l'ultima)."""
    from apps.editions.models import Edizione

    richiedi_staff(request.auth)
    edizione = services.edizione_di_riferimento(edizione_id)
    return {
        "edizioni": Edizione.objects.order_by("-anno"),
        "edizione": edizione,
        "per_zona": services.stats_per_zona(edizione) if edizione else [],
        "globali": services.stats_globali(edizione) if edizione else None,
        "ticket": services.stats_ticket(edizione) if edizione else None,
    }
