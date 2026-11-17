# apps/api/routers/diaries.py
"""Router `/api/v1/diari`: lista, dettaglio, moduli 1–6, allegati, PDF, cambio referenti.

Le transizioni FSM (`/{id}/azioni/{azione}`) e la valutazione (`/{id}/valutazione…`) stanno in
`apps/api/routers/evaluations.py`, montato sullo stesso prefisso.

Regole riusate, mai duplicate: visibilità `apps.diaries.visibility.diari_visibili`, permessi
`apps.diaries.permessi`, servizi `apps.diaries.service` (rinomina, allegati, PDF, referenti),
validazione/serializzazione dei moduli `apps.diaries.serialization` (condivisa con la PWA).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpResponse
from ninja import File, Form, Query, Router, Status, UploadedFile
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination, paginate

from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.permissions import puo_vedere_diario, puo_vedere_valutazione
from apps.api.schemas.diaries import (
    AllegatoSchema,
    AnagraficaModuloSchema,
    AnagraficaResponseSchema,
    AnagraficaSchema,
    CambioCrpRepartoRispostaSchema,
    CambioReferenteBodySchema,
    CambioReferenteRispostaSchema,
    ConflictResponseSchema,
    DiarioDettaglioSchema,
    DiarioListaSchema,
    DiarioRepartoSchema,
    DiarioStatoLeggeroSchema,
    EsitoSpecialitaSchema,
    FiltriDiariSchema,
    ImpresaModuloSchema,
    ImpresaResponseSchema,
    ImpresaSchema,
    MembroSqSchema,
    MissioneModuloSchema,
    MissioneResponseSchema,
    MissioneSchema,
    OpzioneSchema,
    OpzioniModuliDiarioSchema,
    PdfStatoSchema,
    PermessiDiarioSchema,
    PostoAzioneMissioneSchema,
    PostoAzioneSchema,
    PresentazioneModuloSchema,
    PresentazioneResponseSchema,
    PresentazioneSchema,
    ReferenteSchema,
    RelazioneFinaleModuloSchema,
    RelazioneFinaleResponseSchema,
    RelazioneFinaleSchema,
    RelazioneFinaleUpdateSchema,
    RepartoDiariSchema,
    ScadenzeSchema,
    SceltaSchema,
    StatoModuliSchema,
    ValidationErrorResponseSchema,
    ValutazioneSchema,
    VersionedPutSchema,
)
from apps.diaries import permessi

router = Router(tags=["diari"])

_ERR = {403: ErroreSchema, 404: ErroreSchema, 422: ErroreValidazioneSchema}
_ERR_PUT = {
    400: ValidationErrorResponseSchema, 403: ErroreSchema, 404: ErroreSchema,
    409: ConflictResponseSchema, 422: ErroreValidazioneSchema,
}

IDEMPOTENZA_TTL = 24 * 3600


# ---------------------------------------------------------------------------
# Helper comuni
# ---------------------------------------------------------------------------

def _carica_diario(diario_id: int):
    from apps.diaries.models import Diario

    try:
        return Diario.objects.select_related(
            "edizione", "squadriglia__reparto__gruppo__zona", "csq", "crp",
        ).get(pk=diario_id)
    except Diario.DoesNotExist:
        raise HttpError(404, "Diario non trovato") from None


def _diario_visibile(request, diario_id: int):
    """Diario se visibile all'utente (`diari_visibili`): 404 se non esiste, 403 se non visibile."""
    d = _carica_diario(diario_id)
    if not puo_vedere_diario(request.auth, d):
        raise HttpError(403, "Accesso non consentito")
    return d


def _idempotente(request, esegui: Callable[[], Any]):
    """Rigioca la risposta salvata se il client ripete la richiesta con lo stesso
    `Idempotency-Key` (coda offline della PWA/app). Si salvano solo le risposte 2xx, per 24 ore."""
    from django.core.cache import cache

    chiave = request.headers.get("Idempotency-Key", "").strip()
    if not chiave:
        return esegui()
    ck = f"api_idem:{request.auth.pk}:{request.method}:{request.path}:{chiave[:128]}"
    salvata = cache.get(ck)
    if salvata is not None:
        return Status(*salvata)
    risultato = esegui()
    if isinstance(risultato, Status) and 200 <= risultato.status_code < 300:
        corpo = risultato.value
        if hasattr(corpo, "model_dump"):
            corpo = corpo.model_dump(mode="json")
        cache.set(ck, (risultato.status_code, corpo), IDEMPOTENZA_TTL)
        return Status(risultato.status_code, corpo)
    return risultato


def _referente(socio) -> ReferenteSchema | None:
    if socio is None:
        return None
    return ReferenteSchema(id=socio.pk, nome=socio.nome, cognome=socio.cognome)


def _referente_certo(socio) -> ReferenteSchema:
    return ReferenteSchema(id=socio.pk, nome=socio.nome, cognome=socio.cognome)


def _url(nome: str, **kwargs) -> str:
    from django.urls import reverse

    return reverse(f"api-1.0.0:{nome}", kwargs=kwargs)


def _allegato_schema(a) -> AllegatoSchema:
    kw = {"diario_id": a.diario_id, "allegato_id": a.pk}
    anteprima = _url("diari_allegato_anteprima", **kw)
    return AllegatoSchema(
        id=a.pk, modulo=a.modulo, nome=a.nome, mime=a.mime, dimensione=a.dimensione,
        stato_sync=a.stato_sync, creato_at=a.creato_at,
        anteprima_url=anteprima, miniatura_url=f"{anteprima}?lato=320",
        download_url=_url("diari_allegato_file", **kw),
    )


def _permessi(user, d) -> PermessiDiarioSchema:
    return PermessiDiarioSchema(
        puo_modificare_moduli=permessi.puo_modificare_moduli(user, d),
        puo_vedere_relazione=permessi.puo_vedere_relazione(user),
        puo_modificare_relazione=permessi.puo_modificare_relazione(user, d),
        puo_vedere_valutazione=puo_vedere_valutazione(user, d),
        puo_inviare_csq=permessi.puo_inviare_csq(user, d),
        puo_inviare=permessi.puo_inviare(user, d),
        puo_riaprire=permessi.puo_riaprire(user, d),
        puo_cambiare_csq=permessi.puo_cambiare_csq(user, d),
        puo_cambiare_crp=permessi.puo_cambiare_crp(user, d),
        puo_concedere_dilazione=permessi.puo_concedere_dilazione(user, d),
        puo_caricare_allegati=permessi.puo_caricare_allegati(user, d),
        puo_eliminare_allegati=permessi.puo_eliminare_allegati(user, d),
        puo_pdf=permessi.puo_scaricare_pdf(user) and permessi.pdf_disponibile_nello_stato(d),
    )


def _versioni(d, con_relazione: bool) -> dict[str, int]:
    from apps.diaries.models import Anagrafica, Missione, Presentazione, RelazioneFinale

    versioni = {
        "anagrafica": Anagrafica.objects.filter(diario=d).values_list("version", flat=True).first() or 0,
        "presentazione": Presentazione.objects.filter(diario=d)
        .values_list("version", flat=True).first() or 0,
        "impresa_1": 0,
        "impresa_2": 0,
        "missione": Missione.objects.filter(diario=d).values_list("version", flat=True).first() or 0,
    }
    for numero, version in d.imprese.values_list("numero", "version"):
        versioni[f"impresa_{numero}"] = version
    if con_relazione:
        versioni["relazione_finale"] = (
            RelazioneFinale.objects.filter(diario=d).values_list("version", flat=True).first() or 0
        )
    return versioni


def _stato_moduli(user, d) -> StatoModuliSchema:
    from apps.diaries.models import TipoDiario

    numeri = set(d.imprese.values_list("numero", flat=True))
    vede_relazione = permessi.puo_vedere_relazione(user)
    return StatoModuliSchema(
        anagrafica=hasattr(d, "anagrafica"),
        presentazione=hasattr(d, "presentazione"),
        impresa_1=1 in numeri,
        impresa_2=2 in numeri,
        missione=hasattr(d, "missione"),
        relazione_finale=hasattr(d, "relazione_finale") if vede_relazione else None,
        moduli_csq_completi=d.moduli_csq_completi,
        impresa_2_obbligatoria=d.tipo == TipoDiario.NUOVO,
        missione_obbligatoria=d.tipo == TipoDiario.NUOVO,
        versioni=_versioni(d, vede_relazione),
    )


def _scadenze(d) -> ScadenzeSchema:
    return ScadenzeSchema(
        riferimento=d.scadenza_riferimento,
        riferimento_display=d.get_scadenza_riferimento_display(),
        effettiva=d.scadenza_effettiva(),
        evento=d.edizione.scadenza_evento,
        assemblea=d.edizione.scadenza_assemblea,
        dilazionata=d.dilazioni.exists(),
        seconda_scadenza_passata=d.edizione.seconda_scadenza_passata,
    )


def _impresa_schema(impresa, numero: int) -> ImpresaSchema:
    from apps.diaries.serialization import _impresa_data

    data = _impresa_data(impresa)
    return ImpresaSchema(
        numero=numero,
        **{k: v for k, v in data.items() if k not in ("posti_azione", "specialita", "brevetti")},
        posti_azione=[PostoAzioneSchema(**p) for p in data["posti_azione"]],
        specialita=[EsitoSpecialitaSchema(tipo="specialita", **e) for e in data["specialita"]],
        brevetti=[EsitoSpecialitaSchema(tipo="brevetto", **e) for e in data["brevetti"]],
    )


def _impresa_vuota(numero: int) -> ImpresaSchema:
    return ImpresaSchema(
        numero=numero, titolo="", data_inizio=None, data_fine=None, perche="", come="", cosa="",
        link_esterno="", posti_azione=[], specialita=[], brevetti=[],
    )


def _presentazione_schema(pres) -> PresentazioneSchema:
    return PresentazioneSchema(
        cosa_sappiamo_fare=pres.cosa_sappiamo_fare,
        membri=[MembroSqSchema(id=m.pk, nome=m.nome, ruolo=m.ruolo, sentiero=m.sentiero)
                for m in pres.membri.all()],
    )


def _missione_schema(missione) -> MissioneSchema:
    from apps.diaries.serialization import _missione_data

    data = _missione_data(missione)
    return MissioneSchema(
        titolo=data["titolo"],
        data=missione.data,
        descrizione_svolgimento=data["descrizione_svolgimento"],
        posti_azione=[PostoAzioneMissioneSchema(**p) for p in data["posti_azione"]],
    )


def _relazione_schema(rf) -> RelazioneFinaleSchema:
    from apps.diaries.serialization import _relazione_finale_data

    return RelazioneFinaleSchema(**_relazione_finale_data(rf))


def _richiedi_modifica_moduli(user, d) -> None:
    if not permessi.puo_modificare_moduli(user, d):
        raise HttpError(403, "Accesso non consentito")


def _richiedi_modifica_relazione(user, d) -> None:
    from apps.evaluations.actions import StatoNonValido

    if permessi.puo_modificare_relazione(user, d):
        return
    if permessi.is_crp_del_diario(user, d):
        raise StatoNonValido(
            "La relazione del Capo Reparto è disponibile solo dopo che il Capo Squadriglia "
            "ha inviato la propria parte."
        )
    raise HttpError(403, "Accesso non consentito")


# ---------------------------------------------------------------------------
# Lista e filtri
# ---------------------------------------------------------------------------

_ORDINAMENTI: dict[str, tuple[str, ...]] = {
    "squadriglia": ("squadriglia__nome",),
    "reparto": ("squadriglia__reparto__nome", "squadriglia__nome"),
    "gruppo": ("squadriglia__reparto__gruppo__nome", "squadriglia__nome"),
    "zona": ("squadriglia__reparto__gruppo__zona__nome", "squadriglia__nome"),
    "tipo": ("tipo", "squadriglia__nome"),
    "stato": ("stato", "squadriglia__nome"),
    "csq": ("csq__cognome", "csq__nome"),
    "crp": ("crp__cognome", "crp__nome"),
    "edizione": ("edizione__anno", "squadriglia__nome"),
    "aggiornato": ("aggiornato_at",),
}


def _ordina(qs, ordina: str | None):
    if not ordina:
        return qs
    campi: list[str] = []
    for voce in (v.strip() for v in ordina.split(",") if v.strip()):
        desc = voce.startswith("-")
        chiave = voce.lstrip("-")
        if chiave not in _ORDINAMENTI:
            raise HttpError(422, f"Ordinamento non valido: {chiave}. "
                                 f"Valori ammessi: {', '.join(_ORDINAMENTI)}")
        campi += [f"-{c}" if desc else c for c in _ORDINAMENTI[chiave]]
    return qs.order_by(*campi, "pk")


def _filtra(qs, *, edizione_id=None, zona_id=None, gruppo_id=None, reparto_id=None,
            stato=None, tipo=None, specialita=None, q=None):
    from django.db.models import Q

    if edizione_id is not None:
        qs = qs.filter(edizione_id=edizione_id)
    if zona_id is not None:
        qs = qs.filter(squadriglia__reparto__gruppo__zona_id=zona_id)
    if gruppo_id is not None:
        qs = qs.filter(squadriglia__reparto__gruppo_id=gruppo_id)
    if reparto_id is not None:
        qs = qs.filter(squadriglia__reparto_id=reparto_id)
    if stato:
        qs = qs.filter(stato__in=[s.strip() for s in stato.split(",") if s.strip()])
    if tipo:
        qs = qs.filter(tipo=tipo)
    if specialita:
        qs = qs.filter(anagrafica__specialita=specialita)
    if q:
        # Come la ricerca della lista web (cognome/nome di Capo Reparto e Capo Squadriglia),
        # più il nome della squadriglia: ogni parola deve comparire in uno dei campi.
        for parola in q.split():
            qs = qs.filter(
                Q(csq__cognome__icontains=parola) | Q(csq__nome__icontains=parola)
                | Q(crp__cognome__icontains=parola) | Q(crp__nome__icontains=parola)
                | Q(squadriglia__nome__icontains=parola)
            )
    return qs


@router.get("", response=list[DiarioListaSchema], summary="Lista diari visibili (filtri e ordinamento)")
@paginate(LimitOffsetPagination)
def list_diari(
    request,
    edizione_id: int | None = Query(None),
    zona_id: int | None = Query(None),
    gruppo_id: int | None = Query(None),
    reparto_id: int | None = Query(None),
    stato: str | None = Query(None, description="Uno o più stati separati da virgola"),
    tipo: str | None = Query(None),
    specialita: str | None = Query(None, description="Specialità di squadriglia (anagrafica)"),
    q: str | None = Query(None, description="Cerca per nome/cognome dei referenti o squadriglia"),
    ordina: str | None = Query(
        None, description="Campi separati da virgola, `-` per decrescente: " + ", ".join(_ORDINAMENTI),
    ),
):
    """Diari di `diari_visibili` con i filtri della lista web. Paginata (`limit`, `offset`)."""
    from apps.diaries.visibility import diari_visibili

    qs = _filtra(
        diari_visibili(request.auth), edizione_id=edizione_id, zona_id=zona_id,
        gruppo_id=gruppo_id, reparto_id=reparto_id, stato=stato, tipo=tipo,
        specialita=specialita, q=q,
    )
    return _ordina(qs, ordina).prefetch_related("dilazioni")


@router.get("/filtri", response=FiltriDiariSchema, summary="Valori dei filtri della lista diari")
def filtri_diari(request, edizione_id: int | None = Query(None)):
    """Zone, gruppi, reparti e specialità presenti tra i diari visibili (come la lista web)."""
    from apps.diaries.models import StatoDiario, TipoDiario
    from apps.diaries.visibility import diari_visibili
    from apps.editions.models import Edizione

    qs = diari_visibili(request.auth)
    if edizione_id is not None:
        qs = qs.filter(edizione_id=edizione_id)

    def _opzioni(prefisso: str) -> list[OpzioneSchema]:
        righe = (qs.order_by(f"{prefisso}__nome")
                 .values_list(f"{prefisso}__id", f"{prefisso}__nome").distinct())
        return [OpzioneSchema(id=i, nome=n) for i, n in righe if i is not None]

    specialita = sorted(set(
        qs.exclude(anagrafica__specialita="").exclude(anagrafica__specialita__isnull=True)
        .values_list("anagrafica__specialita", flat=True)
    ))
    return FiltriDiariSchema(
        edizioni=[OpzioneSchema(id=e.pk, nome=str(e)) for e in Edizione.objects.all()],
        zone=_opzioni("squadriglia__reparto__gruppo__zona"),
        gruppi=_opzioni("squadriglia__reparto__gruppo"),
        reparti=_opzioni("squadriglia__reparto"),
        specialita=specialita,
        stati=[SceltaSchema(valore=v, etichetta=e) for v, e in StatoDiario.choices],
        tipi=[SceltaSchema(valore=v, etichetta=e) for v, e in TipoDiario.choices],
        ordinamenti=list(_ORDINAMENTI),
    )


@router.get("/moduli/opzioni", response=OpzioniModuliDiarioSchema,
            summary="Scelte dei campi dei moduli e limiti delle foto")
def opzioni_moduli(request):
    """Specialità di squadriglia e individuali, brevetti, ruoli, sentieri, stati delle
    specialità, moduli con foto e lato massimo delle foto (`Impostazioni.allegati_max_px`)."""
    from apps.diaries.models import (
        BREVETTI_COMPETENZA,
        MODULO_FOTO_CHOICES,
        SPECIALITA_INDIVIDUALI,
        SPECIALITA_SQUADRIGLIA,
        RuoloSq,
        SentieroCammino,
        StatoSpecialita,
        TipoDiario,
    )
    from apps.diaries.service import MAX_BYTES_ALLEGATO, MIME_ALLEGATI_CONSENTITI
    from apps.siteconfig.models import Impostazioni

    def _scelte(choices) -> list[SceltaSchema]:
        return [SceltaSchema(valore=v, etichetta=str(e)) for v, e in choices]

    return OpzioniModuliDiarioSchema(
        tipi_diario=_scelte(TipoDiario.choices),
        specialita_squadriglia=list(SPECIALITA_SQUADRIGLIA),
        specialita_individuali=list(SPECIALITA_INDIVIDUALI),
        brevetti=list(BREVETTI_COMPETENZA),
        ruoli_squadriglia=_scelte(RuoloSq.choices),
        sentieri=_scelte(SentieroCammino.choices),
        stati_specialita=_scelte(StatoSpecialita.choices),
        moduli_foto=_scelte(MODULO_FOTO_CHOICES),
        allegati_max_px=Impostazioni.get().allegati_max_px or 1024,
        allegati_max_mb=MAX_BYTES_ALLEGATO // (1024 * 1024),
        allegati_tipi=sorted(MIME_ALLEGATI_CONSENTITI),
    )


@router.get("/reparti/{reparto_id}/cambia-crp", response={200: RepartoDiariSchema, **_ERR},
            summary="Diari non inviati del reparto (per il cambio Capo Reparto in blocco)")
def diari_reparto_cambio_crp(request, reparto_id: int):
    """Solo Admin, Segreteria, Incaricati EG."""
    from apps.diaries.service import diari_cambio_crp_reparto
    from apps.org.models import Reparto

    if not permessi.puo_cambiare_crp_reparto(request.auth):
        raise HttpError(403, "Operazione riservata alla gestione della piattaforma.")
    reparto = Reparto.objects.get(pk=reparto_id)
    return Status(200, RepartoDiariSchema(
        reparto=OpzioneSchema(id=reparto.pk, nome=reparto.nome),
        diari=[
            DiarioRepartoSchema(
                id=d.pk, edizione_anno=d.edizione.anno, squadriglia=d.squadriglia.nome,
                stato=d.stato, stato_display=d.get_stato_display(),
                csq=_referente(d.csq), crp=_referente(d.crp),
            )
            for d in diari_cambio_crp_reparto(reparto)
        ],
    ))


@router.post("/reparti/{reparto_id}/cambia-crp",
             response={200: CambioCrpRepartoRispostaSchema, **_ERR},
             summary="Cambia il Capo Reparto di tutti i diari non inviati del reparto")
def cambia_crp_reparto(request, reparto_id: int, payload: CambioReferenteBodySchema):
    """Solo Admin, Segreteria, Incaricati EG. Il socio deve essere un capo non provvisorio."""
    from apps.diaries import service
    from apps.org.models import Reparto

    if not permessi.puo_cambiare_crp_reparto(request.auth):
        raise HttpError(403, "Operazione riservata alla gestione della piattaforma.")
    reparto = Reparto.objects.get(pk=reparto_id)
    nuovo, n = service.cambia_crp_reparto(reparto, payload.socio_id, request.auth)
    return Status(200, CambioCrpRepartoRispostaSchema(
        detail=f"Capo Reparto aggiornato a {nuovo.cognome} {nuovo.nome} per {n} "
               + ("diario." if n == 1 else "diari."),
        nuovo=_referente_certo(nuovo), diari_aggiornati=n,
    ))


# ---------------------------------------------------------------------------
# Dettaglio
# ---------------------------------------------------------------------------

@router.get("/{diario_id}", response={200: DiarioDettaglioSchema, 403: ErroreSchema, 404: ErroreSchema},
            summary="Dettaglio diario")
def get_diario(request, diario_id: int):
    """Tutto quello che mostra la pagina del diario, con i permessi calcolati per l'interfaccia.

    Relazione finale mai al Capo Squadriglia; valutazione solo se visibile (`puo_vedere_valutazione`).
    """
    from apps.diaries.models import Diario

    try:
        d = Diario.objects.select_related(
            "edizione", "squadriglia__reparto__gruppo__zona", "csq", "crp",
            "anagrafica", "presentazione", "missione", "relazione_finale", "valutazione",
        ).prefetch_related(
            "presentazione__membri", "imprese__posti_azione", "imprese__esiti_specialita",
            "missione__posti_azione", "allegati",
        ).get(pk=diario_id)
    except Diario.DoesNotExist:
        raise HttpError(404, "Diario non trovato") from None

    user = request.auth
    if not puo_vedere_diario(user, d):
        raise HttpError(403, "Accesso non consentito")

    from apps.diaries.serialization import _anagrafica_data, _valutazione_data

    sq = d.squadriglia
    ana = getattr(d, "anagrafica", None)
    pres = getattr(d, "presentazione", None)
    missione = getattr(d, "missione", None)
    rf = getattr(d, "relazione_finale", None)
    val = getattr(d, "valutazione", None)
    drive_url = (f"https://drive.google.com/drive/folders/{d.drive_folder_allegati_id}"
                 if d.drive_folder_allegati_id else None)

    return Status(200, DiarioDettaglioSchema(
        id=d.pk,
        edizione_id=d.edizione_id,
        edizione_anno=d.edizione.anno,
        squadriglia=sq.nome,
        squadriglia_id=sq.pk,
        zona=sq.reparto.gruppo.zona.nome,
        gruppo=sq.reparto.gruppo.nome,
        reparto=sq.reparto.nome,
        reparto_id=sq.reparto_id,
        tipo=d.tipo,
        tipo_display=d.get_tipo_display(),
        stato=d.stato,
        stato_display=d.get_stato_display(),
        scadenza=d.scadenza_effettiva(),
        pubblicato=d.pubblicato,
        drive_folder_url=drive_url,
        anagrafica=AnagraficaSchema(**_anagrafica_data(ana, d)) if ana else None,
        presentazione=_presentazione_schema(pres) if pres else None,
        imprese=[_impresa_schema(i, i.numero) for i in sorted(d.imprese.all(), key=lambda i: i.numero)],
        missione=_missione_schema(missione) if missione else None,
        relazione_finale=_relazione_schema(rf) if rf and permessi.puo_vedere_relazione(user) else None,
        valutazione=ValutazioneSchema(**_valutazione_data(val))
        if val and puo_vedere_valutazione(user, d) else None,
        csq=_referente(d.csq),
        crp=_referente(d.crp),
        scadenze=_scadenze(d),
        stato_moduli=_stato_moduli(user, d),
        permessi=_permessi(user, d),
        allegati=[_allegato_schema(a) for a in d.allegati.all()],
        inviato_at=d.inviato_at,
        csq_completato_at=d.csq_completato_at,
        aggiornato_at=d.aggiornato_at,
    ))


@router.get("/{diario_id}/stato", response={200: DiarioStatoLeggeroSchema, 403: ErroreSchema,
                                            404: ErroreSchema},
            summary="Stato leggero del diario (compilazione offline)")
def get_stato_diario(request, diario_id: int):
    """Equivalente di `GET /api/diari/<pk>/` della PWA, più le versioni dei moduli."""
    d = _diario_visibile(request, diario_id)
    return Status(200, DiarioStatoLeggeroSchema(
        stato=d.stato,
        stato_display=d.get_stato_display(),
        tipo=d.tipo,
        puo_editare=permessi.puo_modificare_moduli(request.auth, d),
        moduli_csq_completi=d.moduli_csq_completi,
        has_anagrafica=hasattr(d, "anagrafica"),
        has_presentazione=hasattr(d, "presentazione"),
        imprese=list(d.imprese.values_list("numero", flat=True)),
        has_missione=hasattr(d, "missione"),
        versioni=_versioni(d, permessi.puo_vedere_relazione(request.auth)),
    ))


@router.get("/{diario_id}/permessi", response={200: PermessiDiarioSchema, 403: ErroreSchema,
                                               404: ErroreSchema},
            summary="Permessi dell'utente corrente sul diario")
def get_permessi_diario(request, diario_id: int):
    d = _diario_visibile(request, diario_id)
    return Status(200, _permessi(request.auth, d))


# ---------------------------------------------------------------------------
# Modulo 1 — Anagrafica
# ---------------------------------------------------------------------------

@router.get("/{diario_id}/anagrafica", response={200: AnagraficaModuloSchema, 403: ErroreSchema,
                                                 404: ErroreSchema},
            summary="Leggi anagrafica (modulo 1)")
def get_anagrafica(request, diario_id: int):
    """Modulo vuoto con `version: 0` se non ancora salvato."""
    from apps.diaries.models import Anagrafica
    from apps.diaries.serialization import _anagrafica_data

    d = _diario_visibile(request, diario_id)
    ana = Anagrafica.objects.filter(diario=d).first() or Anagrafica()
    return Status(200, AnagraficaModuloSchema(
        version=ana.version, data=AnagraficaSchema(**_anagrafica_data(ana, d)),
    ))


@router.put(
    "/{diario_id}/anagrafica",
    response={200: AnagraficaResponseSchema, **_ERR_PUT},
    summary="Aggiorna anagrafica",
)
def put_anagrafica(request, diario_id: int, payload: VersionedPutSchema):
    """Optimistic locking su `version` (409 con `server_version`). Il nome squadriglia
    rinomina anche le cartelle Drive; le email dei referenti le cambia solo lo staff."""
    return _idempotente(request, lambda: _put_anagrafica(request, diario_id, payload))


def _put_anagrafica(request, diario_id: int, payload: VersionedPutSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.diaries.models import Anagrafica
    from apps.diaries.serialization import _anagrafica_data, _apply_anagrafica, _validate_anagrafica
    from apps.diaries.service import inizia_se_necessario

    d = _carica_diario(diario_id)
    user = request.auth
    _richiedi_modifica_moduli(user, d)

    try:
        cleaned = _validate_anagrafica(payload.data, bool(user.is_superuser or user.is_staff_plancia))
    except ValidationError as exc:
        return Status(400, ValidationErrorResponseSchema(error="validation", errors=exc.message_dict))

    with transaction.atomic():
        try:
            anagrafica = Anagrafica.objects.select_for_update().get(diario=d)
            if anagrafica.version != payload.version:
                return Status(409, ConflictResponseSchema(server_version=anagrafica.version))
        except Anagrafica.DoesNotExist:
            if payload.version != 0:
                return Status(409, ConflictResponseSchema(server_version=0))
            anagrafica = Anagrafica(diario=d)

        inizia_se_necessario(d)
        _apply_anagrafica(anagrafica, d, cleaned)
        anagrafica.version = payload.version + 1
        anagrafica.save()

    d.refresh_from_db()
    d.squadriglia.refresh_from_db()
    return Status(200, AnagraficaResponseSchema(
        version=anagrafica.version, data=AnagraficaSchema(**_anagrafica_data(anagrafica, d)),
    ))


# ---------------------------------------------------------------------------
# Modulo 2 — Presentazione
# ---------------------------------------------------------------------------

@router.get("/{diario_id}/presentazione", response={200: PresentazioneModuloSchema,
                                                    403: ErroreSchema, 404: ErroreSchema},
            summary="Leggi presentazione e membri (modulo 2)")
def get_presentazione(request, diario_id: int):
    from apps.diaries.models import Presentazione

    d = _diario_visibile(request, diario_id)
    pres = Presentazione.objects.filter(diario=d).prefetch_related("membri").first()
    if pres is None:
        return Status(200, PresentazioneModuloSchema(
            version=0, data=PresentazioneSchema(cosa_sappiamo_fare="", membri=[]),
        ))
    return Status(200, PresentazioneModuloSchema(version=pres.version, data=_presentazione_schema(pres)))


@router.put(
    "/{diario_id}/presentazione",
    response={200: PresentazioneResponseSchema, **_ERR_PUT},
    summary="Aggiorna presentazione",
)
def put_presentazione(request, diario_id: int, payload: VersionedPutSchema):
    """Membri sincronizzati per `id` (senza id = nuovo, assente = eliminato)."""
    return _idempotente(request, lambda: _put_presentazione(request, diario_id, payload))


def _put_presentazione(request, diario_id: int, payload: VersionedPutSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.diaries.models import MembroSq, Presentazione
    from apps.diaries.serialization import (
        _apply_membro,
        _str_field,
        _sync_nested,
        _validate_membro,
        _validate_nested,
    )
    from apps.diaries.service import inizia_se_necessario

    d = _carica_diario(diario_id)
    _richiedi_modifica_moduli(request.auth, d)

    data = payload.data
    errors: dict = {}
    try:
        cosa_sappiamo_fare = _str_field(data, "cosa_sappiamo_fare", 10000)
    except ValidationError as e:
        errors.update(e.message_dict)
        cosa_sappiamo_fare = ""

    raw_membri = data.get("membri", [])
    if not isinstance(raw_membri, list):
        raise HttpError(400, "membri deve essere una lista")
    cleaned_membri, nested_errs = _validate_nested(raw_membri, _validate_membro)
    if nested_errs:
        errors["membri"] = nested_errs
    if errors:
        return Status(400, ValidationErrorResponseSchema(error="validation", errors=errors))

    with transaction.atomic():
        try:
            pres = Presentazione.objects.select_for_update().get(diario=d)
            if pres.version != payload.version:
                return Status(409, ConflictResponseSchema(server_version=pres.version))
        except Presentazione.DoesNotExist:
            if payload.version != 0:
                return Status(409, ConflictResponseSchema(server_version=0))
            pres = Presentazione(diario=d)
            pres.save()

        inizia_se_necessario(d)
        pres.cosa_sappiamo_fare = cosa_sappiamo_fare
        pres.version = payload.version + 1
        pres.save()
        _sync_nested(
            qs=pres.membri.all(), cleaned_items=cleaned_membri, model_class=MembroSq,
            apply_fn=_apply_membro, presentazione=pres,
        )

    pres.refresh_from_db()
    return Status(200, PresentazioneResponseSchema(version=pres.version, data=_presentazione_schema(pres)))


# ---------------------------------------------------------------------------
# Moduli 3/4 — Imprese
# ---------------------------------------------------------------------------

@router.get("/{diario_id}/imprese/{numero}", response={200: ImpresaModuloSchema, 403: ErroreSchema,
                                                       404: ErroreSchema},
            summary="Leggi impresa 1 o 2 (moduli 3–4)")
def get_impresa(request, diario_id: int, numero: int):
    """Posti d'azione (`chi`/`cosa`), specialità individuali e brevetti con `chi`."""
    from apps.diaries.models import Impresa

    if numero not in (1, 2):
        raise HttpError(404, "Impresa non trovata: numero deve essere 1 o 2")
    d = _diario_visibile(request, diario_id)
    impresa = Impresa.objects.filter(diario=d, numero=numero).first()
    if impresa is None:
        return Status(200, ImpresaModuloSchema(version=0, data=_impresa_vuota(numero)))
    return Status(200, ImpresaModuloSchema(version=impresa.version, data=_impresa_schema(impresa, numero)))


@router.put(
    "/{diario_id}/imprese/{numero}",
    response={200: ImpresaResponseSchema, **_ERR_PUT},
    summary="Aggiorna impresa",
)
def put_impresa(request, diario_id: int, numero: int, payload: VersionedPutSchema):
    """La 2ª impresa è facoltativa per i diari di rinnovo ma sempre compilabile."""
    return _idempotente(request, lambda: _put_impresa(request, diario_id, numero, payload))


def _put_impresa(request, diario_id: int, numero: int, payload: VersionedPutSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.diaries.models import EsitoSpecialita, Impresa, PostoAzione, TipoEsito
    from apps.diaries.serialization import (
        SCELTE_BREVETTI,
        SCELTE_SPECIALITA_IND,
        _apply_esito,
        _apply_posto_azione,
        _date_field,
        _str_field,
        _sync_nested,
        _validate_esito,
        _validate_nested,
        _validate_posto_azione,
    )
    from apps.diaries.service import inizia_se_necessario

    if numero not in (1, 2):
        raise HttpError(400, "numero deve essere 1 o 2")

    d = _carica_diario(diario_id)
    _richiedi_modifica_moduli(request.auth, d)

    data = payload.data
    errors: dict = {}

    def collect(key, fn, *args):
        try:
            return fn(data, key, *args)
        except ValidationError as e:
            errors.update(e.message_dict)
            return None

    titolo = collect("titolo", _str_field, 200) or ""
    data_inizio = collect("data_inizio", _date_field)
    data_fine = collect("data_fine", _date_field)
    perche = collect("perche", _str_field, 10000) or ""
    come = collect("come", _str_field, 10000) or ""
    cosa = collect("cosa", _str_field, 10000) or ""
    link_esterno = collect("link_esterno", _str_field, 200) or ""

    for key in ("posti_azione", "specialita", "brevetti"):
        if not isinstance(data.get(key, []), list):
            raise HttpError(400, f"{key} deve essere una lista")

    cleaned_posti, errs = _validate_nested(data.get("posti_azione", []), _validate_posto_azione)
    if errs:
        errors["posti_azione"] = errs
    cleaned_specialita, errs = _validate_nested(
        data.get("specialita", []), _validate_esito(SCELTE_SPECIALITA_IND)
    )
    if errs:
        errors["specialita"] = errs
    cleaned_brevetti, errs = _validate_nested(data.get("brevetti", []), _validate_esito(SCELTE_BREVETTI))
    if errs:
        errors["brevetti"] = errs
    if errors:
        return Status(400, ValidationErrorResponseSchema(error="validation", errors=errors))

    with transaction.atomic():
        try:
            impresa = Impresa.objects.select_for_update().get(diario=d, numero=numero)
            if impresa.version != payload.version:
                return Status(409, ConflictResponseSchema(server_version=impresa.version))
        except Impresa.DoesNotExist:
            if payload.version != 0:
                return Status(409, ConflictResponseSchema(server_version=0))
            impresa = Impresa(diario=d, numero=numero)
            impresa.save()

        inizia_se_necessario(d)
        impresa.titolo = titolo
        impresa.data_inizio = data_inizio
        impresa.data_fine = data_fine
        impresa.perche = perche
        impresa.come = come
        impresa.cosa = cosa
        impresa.link_esterno = link_esterno
        impresa.version = payload.version + 1
        impresa.save()

        _sync_nested(qs=impresa.posti_azione.all(), cleaned_items=cleaned_posti,
                     model_class=PostoAzione, apply_fn=_apply_posto_azione, impresa=impresa)
        _sync_nested(qs=impresa.esiti_specialita.filter(tipo=TipoEsito.SPECIALITA),
                     cleaned_items=cleaned_specialita, model_class=EsitoSpecialita,
                     apply_fn=_apply_esito(TipoEsito.SPECIALITA), impresa=impresa)
        _sync_nested(qs=impresa.esiti_specialita.filter(tipo=TipoEsito.BREVETTO),
                     cleaned_items=cleaned_brevetti, model_class=EsitoSpecialita,
                     apply_fn=_apply_esito(TipoEsito.BREVETTO), impresa=impresa)

    impresa.refresh_from_db()
    return Status(200, ImpresaResponseSchema(version=impresa.version, data=_impresa_schema(impresa, numero)))


# ---------------------------------------------------------------------------
# Modulo 5 — Missione
# ---------------------------------------------------------------------------

@router.get("/{diario_id}/missione", response={200: MissioneModuloSchema, 403: ErroreSchema,
                                               404: ErroreSchema},
            summary="Leggi missione (modulo 5)")
def get_missione(request, diario_id: int):
    from apps.diaries.models import Missione

    d = _diario_visibile(request, diario_id)
    missione = Missione.objects.filter(diario=d).first() or Missione()
    return Status(200, MissioneModuloSchema(version=missione.version, data=_missione_schema(missione)))


@router.put(
    "/{diario_id}/missione",
    response={200: MissioneResponseSchema, **_ERR_PUT},
    summary="Aggiorna missione",
)
def put_missione(request, diario_id: int, payload: VersionedPutSchema):
    """`posti_azione` (`[{id?, descrizione}]`) è facoltativo: se assente i posti non cambiano."""
    return _idempotente(request, lambda: _put_missione(request, diario_id, payload))


def _put_missione(request, diario_id: int, payload: VersionedPutSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.diaries.models import Missione, PostoAzioneMissione
    from apps.diaries.serialization import (
        _apply_posto_missione,
        _date_field,
        _str_field,
        _sync_nested,
        _validate_nested,
        _validate_posto_missione,
    )
    from apps.diaries.service import inizia_se_necessario

    d = _carica_diario(diario_id)
    _richiedi_modifica_moduli(request.auth, d)

    data = payload.data
    errors: dict = {}

    def collect(key, fn, *args):
        try:
            return fn(data, key, *args)
        except ValidationError as e:
            errors.update(e.message_dict)
            return None

    titolo = collect("titolo", _str_field, 200) or ""
    data_missione = collect("data", _date_field)
    descrizione = collect("descrizione_svolgimento", _str_field, 10000) or ""

    posti = None
    if "posti_azione" in data:
        if not isinstance(data["posti_azione"], list):
            raise HttpError(400, "posti_azione deve essere una lista")
        posti, errs = _validate_nested(data["posti_azione"], _validate_posto_missione)
        if errs:
            errors["posti_azione"] = errs
    if errors:
        return Status(400, ValidationErrorResponseSchema(error="validation", errors=errors))

    with transaction.atomic():
        try:
            missione = Missione.objects.select_for_update().get(diario=d)
            if missione.version != payload.version:
                return Status(409, ConflictResponseSchema(server_version=missione.version))
        except Missione.DoesNotExist:
            if payload.version != 0:
                return Status(409, ConflictResponseSchema(server_version=0))
            missione = Missione(diario=d)

        inizia_se_necessario(d)
        missione.titolo = titolo
        missione.data = data_missione
        missione.descrizione_svolgimento = descrizione
        missione.version = payload.version + 1
        missione.save()
        if posti is not None:
            _sync_nested(qs=missione.posti_azione.all(), cleaned_items=posti,
                         model_class=PostoAzioneMissione, apply_fn=_apply_posto_missione,
                         missione=missione)

    return Status(200, MissioneResponseSchema(version=missione.version, data=_missione_schema(missione)))


# ---------------------------------------------------------------------------
# Modulo 6 — Relazione finale (Capo Reparto)
# ---------------------------------------------------------------------------

@router.get("/{diario_id}/relazione-finale", response={200: RelazioneFinaleModuloSchema, **_ERR},
            summary="Leggi relazione finale (modulo 6, mai al Capo Squadriglia)")
def get_relazione_finale(request, diario_id: int):
    from apps.diaries.models import RelazioneFinale

    d = _diario_visibile(request, diario_id)
    if not permessi.puo_vedere_relazione(request.auth):
        raise HttpError(403, "La relazione finale non è visibile al Capo Squadriglia.")
    rf = RelazioneFinale.objects.filter(diario=d).first() or RelazioneFinale()
    return Status(200, RelazioneFinaleModuloSchema(version=rf.version, data=_relazione_schema(rf)))


@router.put(
    "/{diario_id}/relazione-finale",
    response={200: RelazioneFinaleResponseSchema, **_ERR_PUT},
    summary="Aggiorna relazione finale (solo Capo Reparto)",
)
def put_relazione_finale(request, diario_id: int, payload: RelazioneFinaleUpdateSchema):
    """Capo Reparto del diario in RELAZIONE_FINALE (422 se il Capo Squadriglia non ha ancora
    inviato) o staff. `version` facoltativa: se inviata, 409 sui conflitti."""
    return _idempotente(request, lambda: _put_relazione_finale(request, diario_id, payload))


def _put_relazione_finale(request, diario_id: int, payload: RelazioneFinaleUpdateSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.diaries.models import RelazioneFinale
    from apps.diaries.serialization import _apply_relazione_finale, _validate_relazione_finale

    d = _carica_diario(diario_id)
    _richiedi_modifica_relazione(request.auth, d)

    try:
        cleaned = _validate_relazione_finale(payload.data)
    except ValidationError as exc:
        return Status(400, ValidationErrorResponseSchema(error="validation", errors=exc.message_dict))

    with transaction.atomic():
        rf = RelazioneFinale.objects.select_for_update().filter(diario=d).first()
        server_version = rf.version if rf else 0
        if payload.version is not None and payload.version != server_version:
            return Status(409, ConflictResponseSchema(server_version=server_version))
        if rf is None:
            rf = RelazioneFinale(diario=d)
        _apply_relazione_finale(rf, cleaned)
        rf.version = server_version + 1
        rf.save()

    return Status(200, RelazioneFinaleResponseSchema(version=rf.version, data=_relazione_schema(rf)))


# ---------------------------------------------------------------------------
# Allegati (foto dei moduli impresa_1, impresa_2, missione)
# ---------------------------------------------------------------------------

def _allegato_del_diario(d, allegato_id: int):
    return d.allegati.get(pk=allegato_id)  # DoesNotExist → 404 (gestore globale)


@router.get("/{diario_id}/allegati", response={200: list[AllegatoSchema], 403: ErroreSchema,
                                               404: ErroreSchema},
            summary="Elenco foto del diario")
def list_allegati(request, diario_id: int, modulo: str | None = Query(None)):
    d = _diario_visibile(request, diario_id)
    qs = d.allegati.all()
    if modulo:
        qs = qs.filter(modulo=modulo)
    return Status(200, [_allegato_schema(a) for a in qs])


@router.post("/{diario_id}/allegati", response={201: AllegatoSchema, **_ERR},
             summary="Carica una foto (multipart: modulo, file)")
def upload_allegato(request, diario_id: int, modulo: Form[str], file: File[UploadedFile]):
    """Ridimensionata al lato maggiore `Impostazioni.allegati_max_px`, poi in coda per Drive.
    Primo caricamento: il diario passa da NON_INIZIATO a IN_COMPILAZIONE.
    Con `Idempotency-Key` un nuovo invio della stessa foto non crea un doppione."""
    from apps.diaries.service import carica_allegato

    d = _diario_visibile(request, diario_id)
    return _idempotente(
        request, lambda: Status(201, _allegato_schema(carica_allegato(d, request.auth, modulo, file))),
    )


@router.delete("/{diario_id}/allegati/{allegato_id}", response={204: None, **_ERR},
               summary="Elimina una foto")
def delete_allegato(request, diario_id: int, allegato_id: int):
    """Fino all'invio allo staff (Capo Squadriglia; in RELAZIONE_FINALE anche Capo Reparto);
    lo staff sempre. 404 se la foto non esiste più (per la coda offline vale come eliminata)."""
    from apps.diaries.service import elimina_allegato

    d = _diario_visibile(request, diario_id)
    if not permessi.puo_eliminare_allegati(request.auth, d):
        raise HttpError(403, "Non puoi eliminare foto di questo diario.")
    elimina_allegato(d, _allegato_del_diario(d, allegato_id), request.auth)
    return Status(204, None)


def _risposta_file(contenuto: bytes, mime: str, nome: str, *, allegato: bool) -> HttpResponse:
    response = HttpResponse(contenuto, content_type=mime)
    disp = "attachment" if allegato else "inline"
    response["Content-Disposition"] = f'{disp}; filename="{nome}"'
    response["Content-Length"] = len(contenuto)
    response["Cache-Control"] = "private, max-age=86400"
    return response


@router.get("/{diario_id}/allegati/{allegato_id}/anteprima", response={200: None, **_ERR},
            url_name="diari_allegato_anteprima", summary="Anteprima (o miniatura) di una foto")
def anteprima_allegato(request, diario_id: int, allegato_id: int,
                       lato: int | None = Query(None, ge=32, le=2048,
                                                description="Miniatura: lato maggiore in pixel")):
    """Immagine inline dal file locale o da Drive; con `lato` una miniatura JPEG."""
    from apps.diaries.service import FileNonDisponibile, contenuto_allegato, miniatura

    d = _diario_visibile(request, diario_id)
    a = _allegato_del_diario(d, allegato_id)
    if not a.mime.startswith("image/"):
        raise HttpError(404, "Anteprima non disponibile")
    try:
        contenuto = contenuto_allegato(d, a)
    except FileNonDisponibile as exc:
        raise HttpError(404, str(exc)) from None
    if lato:
        return _risposta_file(miniatura(contenuto, lato), "image/jpeg", a.nome, allegato=False)
    return _risposta_file(contenuto, a.mime, a.nome, allegato=False)


@router.get("/{diario_id}/allegati/{allegato_id}/file", response={200: None, **_ERR},
            url_name="diari_allegato_file", summary="Scarica una foto")
def download_allegato(request, diario_id: int, allegato_id: int):
    from apps.diaries.service import FileNonDisponibile, contenuto_allegato

    d = _diario_visibile(request, diario_id)
    a = _allegato_del_diario(d, allegato_id)
    try:
        contenuto = contenuto_allegato(d, a)
    except FileNonDisponibile as exc:
        raise HttpError(404, str(exc)) from None
    return _risposta_file(contenuto, a.mime or "application/octet-stream", a.nome, allegato=True)


# ---------------------------------------------------------------------------
# PDF (moduli 1–6, mai la valutazione; mai al Capo Squadriglia)
# ---------------------------------------------------------------------------

def _diario_pdf(request, diario_id: int):
    from apps.evaluations.actions import StatoNonValido

    d = _diario_visibile(request, diario_id)
    if not permessi.puo_scaricare_pdf(request.auth):
        raise HttpError(403, "Il PDF del diario non è disponibile per il Capo Squadriglia.")
    if not permessi.pdf_disponibile_nello_stato(d):
        raise StatoNonValido("Il PDF è disponibile solo dopo l'invio del diario allo staff.")
    return d


def _pdf_stato_schema(d, stato: dict, avviato: bool = False) -> PdfStatoSchema:
    from apps.diaries.service import StatoPdf

    return PdfStatoSchema(
        **stato, avviato=avviato,
        download_url=_url("diari_pdf_scarica", diario_id=d.pk)
        if stato["stato"] == StatoPdf.PRONTO else None,
    )


@router.get("/{diario_id}/pdf/stato", response={200: PdfStatoSchema, **_ERR},
            summary="Stato del PDF del diario")
def stato_pdf_diario(request, diario_id: int):
    """`pronto` | `da_generare` | `in_generazione` (lock `pdf_task_lock:{id}`) | `bloccato`
    (generazione massiva in corso per l'edizione)."""
    from apps.diaries.service import stato_pdf

    d = _diario_pdf(request, diario_id)
    return Status(200, _pdf_stato_schema(d, stato_pdf(d)))


@router.post("/{diario_id}/pdf", response={200: PdfStatoSchema, 202: PdfStatoSchema, **_ERR},
             summary="Avvia la generazione del PDF")
def avvia_pdf_diario(request, diario_id: int):
    """Avvia il task Celery (202, mail «in generazione» al richiedente) se il PDF non è pronto,
    non è già in generazione e non è in corso la generazione massiva; altrimenti 200 con lo stato."""
    from apps.diaries.service import avvia_generazione_pdf

    d = _diario_pdf(request, diario_id)
    stato, avviato = avvia_generazione_pdf(d, request.auth)
    return Status((202 if avviato else 200), _pdf_stato_schema(d, stato, avviato))


@router.get("/{diario_id}/pdf", response={200: None, 202: PdfStatoSchema, **_ERR},
            url_name="diari_pdf_scarica", summary="Scarica il PDF (se pronto)")
def scarica_pdf_diario(request, diario_id: int):
    """200 `application/pdf` se pronto (cache Drive, o generato al volo se Drive non è
    configurato); altrimenti 202 con lo stato in JSON (non avvia la generazione: usare POST)."""
    from apps.diaries.service import contenuto_pdf_pronto, stato_pdf

    d = _diario_pdf(request, diario_id)
    try:
        pronto = contenuto_pdf_pronto(d)
    except Exception:  # noqa: BLE001 - errore di WeasyPrint nella generazione sincrona
        raise HttpError(500, "Errore nella generazione del PDF.") from None
    if pronto is None:
        return Status(202, _pdf_stato_schema(d, stato_pdf(d)))
    contenuto, nome = pronto
    return _risposta_file(contenuto, "application/pdf", nome, allegato=True)


# ---------------------------------------------------------------------------
# Cambio referenti del singolo diario
# ---------------------------------------------------------------------------

@router.post("/{diario_id}/cambia-csq", response={200: CambioReferenteRispostaSchema, **_ERR},
             summary="Cambia il Capo Squadriglia del diario")
def cambia_csq(request, diario_id: int, payload: CambioReferenteBodySchema):
    """Capo Reparto del diario (NON_INIZIATO/IN_COMPILAZIONE) o staff (prima dell'invio).
    Il socio deve essere un ragazzo non provvisorio (422 altrimenti)."""
    from apps.diaries import service

    d = _diario_visibile(request, diario_id)
    nuovo, vecchio = service.cambia_csq(d, payload.socio_id, request.auth)
    nota = f" (sostituisce {vecchio.cognome} {vecchio.nome})" if vecchio else ""
    return Status(200, CambioReferenteRispostaSchema(
        detail=f"Capo Squadriglia aggiornato: {nuovo.cognome} {nuovo.nome}{nota}.",
        nuovo=_referente_certo(nuovo), precedente=_referente(vecchio),
    ))


@router.post("/{diario_id}/cambia-crp", response={200: CambioReferenteRispostaSchema, **_ERR},
             summary="Cambia il Capo Reparto del diario")
def cambia_crp(request, diario_id: int, payload: CambioReferenteBodySchema):
    """Solo staff, prima dell'invio. Il socio deve essere un capo non provvisorio (422 altrimenti)."""
    from apps.diaries import service

    d = _diario_visibile(request, diario_id)
    nuovo, vecchio = service.cambia_crp(d, payload.socio_id, request.auth)
    nota = f" (sostituisce {vecchio.cognome} {vecchio.nome})" if vecchio else ""
    return Status(200, CambioReferenteRispostaSchema(
        detail=f"Capo Reparto aggiornato: {nuovo.cognome} {nuovo.nome}{nota}.",
        nuovo=_referente_certo(nuovo), precedente=_referente(vecchio),
    ))
