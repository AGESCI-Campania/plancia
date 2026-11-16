"""Edizioni: elenco, home (edizione attiva), gestione, stato, dilazioni, esiti ed export.

Le regole stanno in `apps.editions.services` (permessi staff, FSM, dilazioni, export) e in
`apps.evaluations.actions` (pubblicazione degli esiti): qui solo traduzione HTTP.
"""
from __future__ import annotations

from django.forms.models import model_to_dict
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Query, Router, Status
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination, paginate

from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.permissions import richiedi_ruolo, richiedi_staff
from apps.api.schemas.editions import (
    DilazioneInSchema,
    DilazioneSchema,
    EdizioneAttivaSchema,
    EdizioneInSchema,
    EdizioneSchema,
    ExportAvviatoSchema,
    PubblicaEsitiSchema,
    RiepilogoEdizioneSchema,
)

router = Router(tags=["edizioni"])

_ERRORI = {403: ErroreSchema, 404: ErroreSchema}
_ERRORI_SCRITTURA = {**_ERRORI, 422: ErroreValidazioneSchema}

#: percorso API → azione del servizio
_AZIONI_STATO = {"apri": "apri", "avvia-valutazione": "avvia_valutazione", "chiudi": "chiudi"}

_CAMPI_FORM = (
    "anno", "stato", "scadenza_evento", "scadenza_assemblea",
    "data_evento_inizio", "data_evento_fine", "evento_comune", "evento_localita",
)


def _edizione_schema(e) -> EdizioneSchema:
    return EdizioneSchema(
        id=e.pk,
        anno=e.anno,
        stato=e.stato,
        stato_display=e.get_stato_display(),
        scadenza_evento=e.scadenza_evento,
        scadenza_assemblea=e.scadenza_assemblea,
        data_evento_inizio=e.data_evento_inizio,
        data_evento_fine=e.data_evento_fine,
        evento_comune=e.evento_comune,
        evento_localita=e.evento_localita,
        scadenza_corrente=e.scadenza_corrente,
        seconda_scadenza_passata=e.seconda_scadenza_passata,
        cartelle_configurate=e.cartelle_configurate,
    )


def _riepilogo_schema(edizione, user) -> RiepilogoEdizioneSchema:
    from apps.editions.services import riepilogo_edizione

    dati = riepilogo_edizione(edizione, user)
    dati["edizione"] = _edizione_schema(edizione)
    return RiepilogoEdizioneSchema(**dati)


def _get_edizione(edizione_id: int):
    from apps.editions.models import Edizione

    return get_object_or_404(Edizione, pk=edizione_id)


def _dati_form(payload: EdizioneInSchema, base: dict) -> dict:
    dati = dict(base)
    for campo, valore in payload.dict(exclude_unset=True).items():
        dati[campo] = "" if valore is None and campo in ("evento_comune", "evento_localita") else valore
    return dati


# ---------------------------------------------------------------------------
# Lettura
# ---------------------------------------------------------------------------

@router.get("", response=list[EdizioneSchema], summary="Lista edizioni")
def list_edizioni(request):
    from apps.editions.models import Edizione

    return [_edizione_schema(e) for e in Edizione.objects.all()]


@router.get(
    "/attiva", response=EdizioneAttivaSchema,
    summary="Edizione attiva (home): riepilogo per il ruolo attivo",
)
def edizione_attiva(request):
    """L'edizione aperta o in valutazione più recente, con i riepiloghi visibili all'utente.

    `riepilogo` è `null` se non c'è un'edizione attiva (la home mostra la pagina informativa;
    `puo_gestire` indica se proporre la creazione di una nuova edizione).
    """
    from apps.editions.services import edizione_attiva as _attiva
    from apps.editions.services import puo_gestire_edizioni

    edizione = _attiva()
    return EdizioneAttivaSchema(
        riepilogo=_riepilogo_schema(edizione, request.auth) if edizione else None,
        puo_gestire=puo_gestire_edizioni(request.auth),
    )


@router.get("/{edizione_id}", response=EdizioneSchema, summary="Dettaglio edizione")
def get_edizione(request, edizione_id: int):
    return _edizione_schema(_get_edizione(edizione_id))


@router.get(
    "/{edizione_id}/riepilogo", response={200: RiepilogoEdizioneSchema, 404: ErroreSchema},
    summary="Riepilogo edizione per il ruolo attivo",
)
def riepilogo(request, edizione_id: int):
    """Totale dei diari visibili, filtri disponibili e (solo staff) conteggi per stato."""
    return _riepilogo_schema(_get_edizione(edizione_id), request.auth)


# ---------------------------------------------------------------------------
# Gestione (staff)
# ---------------------------------------------------------------------------

@router.post(
    "", response={201: EdizioneSchema, **_ERRORI_SCRITTURA}, summary="Crea edizione",
)
def crea_edizione(request, payload: EdizioneInSchema):
    from apps.editions.models import StatoEdizione
    from apps.editions.services import salva_edizione

    richiedi_staff(request.auth)
    dati = _dati_form(payload, {"stato": StatoEdizione.BOZZA, "evento_comune": "",
                                "evento_localita": ""})
    return Status(201, _edizione_schema(salva_edizione(request.auth, dati)))


@router.patch(
    "/{edizione_id}", response={200: EdizioneSchema, **_ERRORI_SCRITTURA},
    summary="Modifica edizione",
)
def modifica_edizione(request, edizione_id: int, payload: EdizioneInSchema):
    from apps.editions.services import salva_edizione

    richiedi_staff(request.auth)
    edizione = _get_edizione(edizione_id)
    dati = _dati_form(payload, model_to_dict(edizione, fields=_CAMPI_FORM))
    return _edizione_schema(salva_edizione(request.auth, dati, edizione))


@router.post(
    "/{edizione_id}/azioni/{azione}", response={200: EdizioneSchema, **_ERRORI_SCRITTURA},
    summary="Cambia stato dell'edizione (apri, avvia-valutazione, chiudi)",
)
def cambia_stato(request, edizione_id: int, azione: str):
    """Bozza → aperta → in valutazione → chiusa."""
    from apps.editions.services import cambia_stato_edizione

    richiedi_staff(request.auth)
    if azione not in _AZIONI_STATO:
        raise HttpError(404, f"Azione non valida. Valori ammessi: {', '.join(_AZIONI_STATO)}")
    edizione = _get_edizione(edizione_id)
    cambia_stato_edizione(edizione, _AZIONI_STATO[azione], request.auth)
    return _edizione_schema(edizione)


# ---------------------------------------------------------------------------
# Dilazioni (staff)
# ---------------------------------------------------------------------------

def _dilazione_schema(d) -> DilazioneSchema:
    return DilazioneSchema(
        id=d.pk,
        diario_id=d.diario_id,
        squadriglia=d.diario.squadriglia.nome,
        nuova_scadenza=d.nuova_scadenza,
        motivazione=d.motivazione,
        concessa_da=(d.concessa_da.get_full_name() or d.concessa_da.email) if d.concessa_da else None,
        creata_at=d.creata_at,
    )


@router.get(
    "/{edizione_id}/dilazioni", response={200: list[DilazioneSchema], **_ERRORI},
    summary="Dilazioni concesse nell'edizione",
)
@paginate(LimitOffsetPagination)
def list_dilazioni(request, edizione_id: int, diario_id: int | None = Query(None)):
    from apps.editions.models import Dilazione

    richiedi_staff(request.auth)
    edizione = _get_edizione(edizione_id)
    qs = Dilazione.objects.filter(diario__edizione=edizione).select_related(
        "diario__squadriglia", "concessa_da"
    )
    if diario_id is not None:
        qs = qs.filter(diario_id=diario_id)
    return [_dilazione_schema(d) for d in qs]


@router.post(
    "/{edizione_id}/dilazioni", response={201: DilazioneSchema, **_ERRORI_SCRITTURA},
    summary="Concedi una dilazione a un diario",
)
def crea_dilazione(request, edizione_id: int, payload: DilazioneInSchema):
    """Solo prima dell'invio del diario allo staff (non iniziato, in compilazione,
    relazione finale)."""
    from apps.diaries.models import Diario
    from apps.editions.services import concedi_dilazione

    richiedi_staff(request.auth)
    edizione = _get_edizione(edizione_id)
    diario = get_object_or_404(Diario, pk=payload.diario_id, edizione=edizione)
    dilazione = concedi_dilazione(diario, request.auth, {
        "nuova_scadenza": payload.nuova_scadenza, "motivazione": payload.motivazione,
    })
    return Status(201, _dilazione_schema(dilazione))


# ---------------------------------------------------------------------------
# Esiti
# ---------------------------------------------------------------------------

@router.post(
    "/{edizione_id}/pubblica-esiti", response={200: PubblicaEsitiSchema, **_ERRORI_SCRITTURA},
    summary="Pubblica tutti gli esiti confermati dell'edizione",
)
def pubblica_esiti(request, edizione_id: int, scadenza: str | None = Query(None)):
    """Incaricato EG / Admin. `?scadenza=prima|seconda` facoltativa: limita ai diari di
    quella scadenza."""
    from apps.accounts.models import Ruolo
    from apps.diaries.models import ScadenzaRiferimento
    from apps.evaluations.actions import pubblica_tutti

    richiedi_ruolo(request.auth, Ruolo.INCARICATO_EG, Ruolo.ADMIN)
    edizione = _get_edizione(edizione_id)
    if scadenza and scadenza not in ScadenzaRiferimento.values:
        from django.core.exceptions import ValidationError

        raise ValidationError({"scadenza": ["Scadenza non valida."]})
    return PubblicaEsitiSchema(pubblicati=pubblica_tutti(edizione, request.auth, scadenza or None))


@router.get(
    "/{edizione_id}/esiti-excel", response=_ERRORI,
    summary="Scarica l'Excel degli esiti (xlsx)",
)
def esiti_excel(request, edizione_id: int):
    from apps.editions.services import nome_excel_esiti
    from apps.exports.service import genera_excel_edizione

    richiedi_staff(request.auth)
    edizione = _get_edizione(edizione_id)
    excel = genera_excel_edizione(edizione)
    response = HttpResponse(
        excel, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{nome_excel_esiti(edizione)}"'
    response["Content-Length"] = len(excel)
    return response


@router.get(
    "/{edizione_id}/export-diari", response={202: ExportAvviatoSchema, **_ERRORI},
    summary="Export riassuntivo dei diari (xlsx, ods, csv)",
)
def export_diari(request, edizione_id: int, formato: str = Query("xlsx")):
    """200 con il file se i diari sono sotto `EXPORT_DIARI_SOGLIA_ASYNC` (il CSV sempre);
    altrimenti 202: il file viene preparato in background e inviato via email."""
    from apps.editions.services import esporta_diari

    richiedi_staff(request.auth)
    edizione = _get_edizione(edizione_id)
    esito = esporta_diari(edizione, request.auth, formato)
    if esito.asincrono:
        return Status(202, ExportAvviatoSchema(
            detail=(f"L'export ({esito.formato.upper()}) di {esito.n_diari} diari è in "
                    "preparazione. Riceverai il file via email appena pronto."),
            formato=esito.formato,
            diari=esito.n_diari,
        ))
    response = HttpResponse(esito.contenuto, content_type=esito.content_type)
    response["Content-Disposition"] = f'attachment; filename="{esito.filename}"'
    response["Content-Length"] = len(esito.contenuto)
    return response
