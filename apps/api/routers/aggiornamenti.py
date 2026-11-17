"""Aggiornamento del server dal web: solo Admin. Logica in `apps.aggiornamenti.services`.

Contratto dei file con il runner sull'host e flusso di riautenticazione della SPA:
`docs/api/aggiornamenti.md`.
"""
from __future__ import annotations

from ninja import Router, Status
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination, paginate

from apps.aggiornamenti import services
from apps.aggiornamenti.models import ReleaseGitHub, RichiestaAggiornamento
from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.permissions import richiedi_admin
from apps.api.schemas.aggiornamenti import (
    AggiornamentiSchema,
    RiautenticazioneSchema,
    RichiestaIn,
    RichiestaSchema,
    StatoAggiornamentoSchema,
)
from apps.siteconfig.versione import versione_installata

router = Router(tags=["aggiornamenti"])

_ERRORI = {401: ErroreSchema, 403: ErroreSchema, 404: ErroreSchema, 422: ErroreValidazioneSchema}


def _riepilogo() -> dict:
    release = ReleaseGitHub.get()
    services.sincronizza_storico()
    return {
        "installata": versione_installata(),
        "ultima": release if (release.versione or release.controllata_at) else None,
        "aggiornamento_disponibile": services.aggiornamento_disponibile(release),
        "richiesta_in_corso": services.richiesta_aperta(),
    }


@router.get("", response={200: AggiornamentiSchema, **_ERRORI},
            summary="Versione installata, ultima release disponibile e richiesta in corso")
def riepilogo(request):
    richiedi_admin(request.auth)
    return _riepilogo()


@router.post("/controlla", response={200: AggiornamentiSchema, **_ERRORI},
             summary="Controlla subito l'ultima release su GitHub")
def controlla(request):
    """Esegue in modo sincrono lo stesso controllo del task giornaliero (timeout 10 s);
    un errore di GitHub non è un errore HTTP: finisce in `ultima.errore`."""
    richiedi_admin(request.auth)
    services.controlla_ultima_release()
    return _riepilogo()


@router.post(
    "/richiesta",
    response={201: RichiestaSchema, 401: RiautenticazioneSchema, 403: ErroreSchema,
              409: ErroreSchema, 422: ErroreValidazioneSchema, 503: ErroreSchema},
    summary="Richiedi l'aggiornamento del server all'ultima release",
)
def richiedi(request, dati: RichiestaIn):
    """Richiede una riautenticazione recente (allauth headless): altrimenti 401 con
    `riautenticazione_richiesta: true`. Scrive `richiesta.json` per il runner sull'host."""
    richiedi_admin(request.auth)
    if not services.autenticazione_recente(request, request.auth):
        return Status(401, {
            "detail": "Per aggiornare il server conferma la tua identità.",
            "riautenticazione_richiesta": True,
            "flussi": services.flussi_riautenticazione(request.auth),
        })
    try:
        richiesta = services.crea_richiesta(request.auth, dati.versione)
    except services.RichiestaInCorso as exc:
        raise HttpError(409, str(exc)) from None
    except services.CartellaNonScrivibile as exc:
        raise HttpError(503, str(exc)) from None
    return Status(201, richiesta)


@router.post("/richiesta/annulla", response={200: RichiestaSchema, 409: ErroreSchema, **_ERRORI},
             summary="Annulla la richiesta non ancora presa in carico dal server")
def annulla(request):
    richiedi_admin(request.auth)
    try:
        return services.annulla_richiesta(request.auth)
    except services.RichiestaInCorso as exc:
        raise HttpError(409, str(exc)) from None


@router.get("/stato", response={200: StatoAggiornamentoSchema, **_ERRORI},
            summary="Avanzamento dell'aggiornamento (da stato.json) e aggiornamento dello storico")
def stato(request):
    """Da interrogare a intervalli durante l'aggiornamento: resta raggiungibile anche in
    manutenzione. Quando i container ripartono, `installata` diventa la nuova versione."""
    richiedi_admin(request.auth)
    stato_file = services.leggi_stato()
    richiesta = services.sincronizza_storico(stato_file)
    return {
        "installata": versione_installata(),
        "richiesta": richiesta,
        "stato": stato_file,
        "in_corso": bool(richiesta and richiesta.aperta),
    }


@router.get("/storico", response={200: list[RichiestaSchema], **_ERRORI},
            summary="Storico delle richieste di aggiornamento (audit)")
@paginate(LimitOffsetPagination)
def storico(request):
    richiedi_admin(request.auth)
    return RichiestaAggiornamento.objects.all()
