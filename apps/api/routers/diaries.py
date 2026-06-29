# apps/api/routers/diaries.py

from ninja import Query, Router
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination, paginate

from apps.api.permissions import (
    is_staff_plancia,
    puo_editare_diario,
    puo_editare_relazione_finale,
    puo_vedere_diario,
    puo_vedere_valutazione,
)
from apps.api.schemas.diaries import (
    AnagraficaResponseSchema,
    ConflictResponseSchema,
    DiarioDetailSchema,
    DiarioListSchema,
    ImpresaResponseSchema,
    MissioneResponseSchema,
    PresentazioneResponseSchema,
    RelazioneFinaleResponseSchema,
    RelazioneFinaleUpdateSchema,
    ValidationErrorResponseSchema,
    VersionedPutSchema,
)

router = Router(tags=["diari"])


def _diario_list_schema(d) -> DiarioListSchema:
    sq = d.squadriglia
    return DiarioListSchema(
        id=d.pk,
        edizione_id=d.edizione_id,
        edizione_anno=d.edizione.anno,
        squadriglia=sq.nome,
        zona=sq.reparto.gruppo.zona.nome,
        gruppo=sq.reparto.gruppo.nome,
        reparto=sq.reparto.nome,
        tipo=d.tipo,
        tipo_display=d.get_tipo_display(),
        stato=d.stato,
        stato_display=d.get_stato_display(),
        scadenza=d.scadenza_effettiva(),
        pubblicato=d.pubblicato,
    )


@router.get("", response=list[DiarioListSchema], summary="Lista diari visibili")
@paginate(LimitOffsetPagination)
def list_diari(
    request,
    edizione_id: int | None = Query(None),
    stato: str | None = Query(None),
    tipo: str | None = Query(None),
):
    from apps.diaries.visibility import diari_visibili

    qs = diari_visibili(request.auth)
    if edizione_id is not None:
        qs = qs.filter(edizione_id=edizione_id)
    if stato:
        qs = qs.filter(stato=stato)
    if tipo:
        qs = qs.filter(tipo=tipo)
    return [_diario_list_schema(d) for d in qs]


@router.get("/{diario_id}", response=DiarioDetailSchema, summary="Dettaglio diario")
def get_diario(request, diario_id: int):
    from ninja.errors import HttpError

    from apps.diaries.models import Diario
    from apps.diaries.serialization import (
        _anagrafica_data,
        _impresa_data,
        _relazione_finale_data,
        _valutazione_data,
    )

    try:
        d = Diario.objects.select_related(
            "edizione",
            "squadriglia__reparto__gruppo__zona",
            "csq", "crp",
            "anagrafica", "presentazione",
            "missione", "relazione_finale", "valutazione",
        ).prefetch_related(
            "presentazione__membri",
            "imprese__posti_azione",
            "imprese__esiti_specialita",
            "missione__posti_azione_missione",
        ).get(pk=diario_id)
    except Diario.DoesNotExist:
        raise HttpError(404, "Diario non trovato") from None

    user = request.auth
    if not puo_vedere_diario(user, d):
        raise HttpError(403, "Accesso non consentito")

    sq = d.squadriglia
    mostra_relazione = user.ruolo != "csq"
    mostra_valutazione = puo_vedere_valutazione(user, d)

    drive_url = None
    if d.drive_folder_allegati_id:
        drive_url = f"https://drive.google.com/drive/folders/{d.drive_folder_allegati_id}"

    ana = getattr(d, "anagrafica", None)
    pres = getattr(d, "presentazione", None)
    missione = getattr(d, "missione", None)
    rf = getattr(d, "relazione_finale", None)
    val = getattr(d, "valutazione", None)

    imprese_data = []
    for imp in sorted(d.imprese.all(), key=lambda i: i.numero):
        imp_dict = _impresa_data(imp)
        imp_dict["numero"] = imp.numero
        imprese_data.append(imp_dict)

    from apps.api.schemas.diaries import (
        AnagraficaSchema,
        EsitoSpecialitaSchema,
        ImpresaSchema,
        MembroSqSchema,
        MissioneSchema,
        PostoAzioneMissioneSchema,
        PostoAzioneSchema,
        PresentazioneSchema,
        RelazioneFinaleSchema,
        ValutazioneSchema,
    )

    def _build_impresa(data: dict) -> ImpresaSchema:
        return ImpresaSchema(
            numero=data["numero"],
            titolo=data["titolo"],
            data_inizio=data["data_inizio"],
            data_fine=data["data_fine"],
            perche=data["perche"],
            come=data["come"],
            cosa=data["cosa"],
            link_esterno=data["link_esterno"],
            posti_azione=[PostoAzioneSchema(**p) for p in data["posti_azione"]],
            specialita=[EsitoSpecialitaSchema(tipo="specialita", **e) for e in data["specialita"]],
            brevetti=[EsitoSpecialitaSchema(tipo="brevetto", **e) for e in data["brevetti"]],
        )

    return DiarioDetailSchema(
        id=d.pk,
        edizione_id=d.edizione_id,
        edizione_anno=d.edizione.anno,
        squadriglia=sq.nome,
        zona=sq.reparto.gruppo.zona.nome,
        gruppo=sq.reparto.gruppo.nome,
        reparto=sq.reparto.nome,
        tipo=d.tipo,
        tipo_display=d.get_tipo_display(),
        stato=d.stato,
        stato_display=d.get_stato_display(),
        scadenza=d.scadenza_effettiva(),
        pubblicato=d.pubblicato,
        drive_folder_url=drive_url,
        anagrafica=AnagraficaSchema(**_anagrafica_data(ana, d)) if ana else None,
        presentazione=PresentazioneSchema(
            cosa_sappiamo_fare=pres.cosa_sappiamo_fare,
            membri=[MembroSqSchema(id=m.pk, nome=m.nome, ruolo=m.ruolo, sentiero=m.sentiero)
                    for m in pres.membri.all()],
        ) if pres else None,
        imprese=[_build_impresa(i) for i in imprese_data],
        missione=MissioneSchema(
            titolo=missione.titolo,
            data=missione.data,
            descrizione_svolgimento=missione.descrizione_svolgimento,
            posti_azione=[PostoAzioneMissioneSchema(descrizione=p.descrizione)
                          for p in missione.posti_azione_missione.all()],
        ) if missione else None,
        relazione_finale=RelazioneFinaleSchema(**_relazione_finale_data(rf))
            if rf and mostra_relazione else None,
        valutazione=ValutazioneSchema(**_valutazione_data(val))
            if val and mostra_valutazione else None,
    )


# ---------------------------------------------------------------------------
# Helpers write
# ---------------------------------------------------------------------------

def _get_diario_write(diario_id: int):
    from apps.diaries.models import Diario
    try:
        return Diario.objects.select_related(
            "edizione", "squadriglia", "csq", "crp"
        ).get(pk=diario_id)
    except Diario.DoesNotExist:
        raise HttpError(404, "Diario non trovato") from None


def _inizia_se_necessario(diario) -> None:
    from apps.diaries.models import StatoDiario
    if diario.stato == StatoDiario.NON_INIZIATO:
        diario.inizia()


# ---------------------------------------------------------------------------
# PUT /api/v1/diari/{diario_id}/anagrafica
# ---------------------------------------------------------------------------

@router.put(
    "/{diario_id}/anagrafica",
    response={200: AnagraficaResponseSchema, 400: ValidationErrorResponseSchema, 409: ConflictResponseSchema},
    summary="Aggiorna anagrafica",
)
def put_anagrafica(request, diario_id: int, payload: VersionedPutSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.api.schemas.diaries import AnagraficaSchema
    from apps.diaries.models import Anagrafica
    from apps.diaries.serialization import (
        _anagrafica_data,
        _apply_anagrafica,
        _validate_anagrafica,
    )

    d = _get_diario_write(diario_id)
    user = request.auth
    if not (is_staff_plancia(user) or puo_editare_diario(user, d)):
        raise HttpError(403, "Accesso non consentito")

    try:
        cleaned = _validate_anagrafica(payload.data, is_staff_plancia(user))
    except ValidationError as exc:
        return 400, ValidationErrorResponseSchema(error="validation", errors=exc.message_dict)

    with transaction.atomic():
        try:
            anagrafica = Anagrafica.objects.select_for_update().get(diario=d)
            if anagrafica.version != payload.version:
                return 409, ConflictResponseSchema(server_version=anagrafica.version)
        except Anagrafica.DoesNotExist:
            if payload.version != 0:
                return 409, ConflictResponseSchema(server_version=0)
            anagrafica = Anagrafica(diario=d)

        _inizia_se_necessario(d)
        _apply_anagrafica(anagrafica, d, cleaned)
        anagrafica.version = payload.version + 1
        anagrafica.save()

    d.refresh_from_db()
    d.squadriglia.refresh_from_db()
    return 200, AnagraficaResponseSchema(
        version=anagrafica.version,
        data=AnagraficaSchema(**_anagrafica_data(anagrafica, d)),
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/diari/{diario_id}/presentazione
# ---------------------------------------------------------------------------

@router.put(
    "/{diario_id}/presentazione",
    response={200: PresentazioneResponseSchema, 400: ValidationErrorResponseSchema, 409: ConflictResponseSchema},
    summary="Aggiorna presentazione",
)
def put_presentazione(request, diario_id: int, payload: VersionedPutSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.api.schemas.diaries import MembroSqSchema, PresentazioneSchema
    from apps.diaries.models import MembroSq, Presentazione
    from apps.diaries.serialization import (
        _apply_membro,
        _str_field,
        _sync_nested,
        _validate_membro,
        _validate_nested,
    )

    d = _get_diario_write(diario_id)
    user = request.auth
    if not (is_staff_plancia(user) or puo_editare_diario(user, d)):
        raise HttpError(403, "Accesso non consentito")

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
        return 400, ValidationErrorResponseSchema(error="validation", errors=errors)

    with transaction.atomic():
        try:
            pres = Presentazione.objects.select_for_update().get(diario=d)
            if pres.version != payload.version:
                return 409, ConflictResponseSchema(server_version=pres.version)
        except Presentazione.DoesNotExist:
            if payload.version != 0:
                return 409, ConflictResponseSchema(server_version=0)
            pres = Presentazione(diario=d)
            pres.save()

        _inizia_se_necessario(d)
        pres.cosa_sappiamo_fare = cosa_sappiamo_fare
        pres.version = payload.version + 1
        pres.save()

        _sync_nested(
            qs=pres.membri.all(),
            cleaned_items=cleaned_membri,
            model_class=MembroSq,
            apply_fn=_apply_membro,
            presentazione=pres,
        )

    pres.refresh_from_db()
    return 200, PresentazioneResponseSchema(
        version=pres.version,
        data=PresentazioneSchema(
            cosa_sappiamo_fare=pres.cosa_sappiamo_fare,
            membri=[MembroSqSchema(id=m.pk, nome=m.nome, ruolo=m.ruolo, sentiero=m.sentiero)
                    for m in pres.membri.all()],
        ),
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/diari/{diario_id}/imprese/{numero}
# ---------------------------------------------------------------------------

@router.put(
    "/{diario_id}/imprese/{numero}",
    response={200: ImpresaResponseSchema, 400: ValidationErrorResponseSchema, 409: ConflictResponseSchema},
    summary="Aggiorna impresa",
)
def put_impresa(request, diario_id: int, numero: int, payload: VersionedPutSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.api.schemas.diaries import EsitoSpecialitaSchema, ImpresaSchema, PostoAzioneSchema
    from apps.diaries.models import EsitoSpecialita, Impresa, PostoAzione, TipoEsito
    from apps.diaries.serialization import (
        SCELTE_BREVETTI,
        SCELTE_SPECIALITA_IND,
        _apply_esito,
        _apply_posto_azione,
        _date_field,
        _impresa_data,
        _str_field,
        _sync_nested,
        _validate_esito,
        _validate_nested,
        _validate_posto_azione,
    )

    if numero not in (1, 2):
        raise HttpError(400, "numero deve essere 1 o 2")

    d = _get_diario_write(diario_id)
    user = request.auth
    if not (is_staff_plancia(user) or puo_editare_diario(user, d)):
        raise HttpError(403, "Accesso non consentito")

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
    cleaned_brevetti, errs = _validate_nested(
        data.get("brevetti", []), _validate_esito(SCELTE_BREVETTI)
    )
    if errs:
        errors["brevetti"] = errs

    if errors:
        return 400, ValidationErrorResponseSchema(error="validation", errors=errors)

    with transaction.atomic():
        try:
            impresa = Impresa.objects.select_for_update().get(diario=d, numero=numero)
            if impresa.version != payload.version:
                return 409, ConflictResponseSchema(server_version=impresa.version)
        except Impresa.DoesNotExist:
            if payload.version != 0:
                return 409, ConflictResponseSchema(server_version=0)
            impresa = Impresa(diario=d, numero=numero)
            impresa.save()

        _inizia_se_necessario(d)
        impresa.titolo = titolo
        impresa.data_inizio = data_inizio
        impresa.data_fine = data_fine
        impresa.perche = perche
        impresa.come = come
        impresa.cosa = cosa
        impresa.link_esterno = link_esterno
        impresa.version = payload.version + 1
        impresa.save()

        _sync_nested(
            qs=impresa.posti_azione.all(),
            cleaned_items=cleaned_posti,
            model_class=PostoAzione,
            apply_fn=_apply_posto_azione,
            impresa=impresa,
        )
        _sync_nested(
            qs=impresa.esiti_specialita.filter(tipo=TipoEsito.SPECIALITA),
            cleaned_items=cleaned_specialita,
            model_class=EsitoSpecialita,
            apply_fn=_apply_esito(TipoEsito.SPECIALITA),
            impresa=impresa,
        )
        _sync_nested(
            qs=impresa.esiti_specialita.filter(tipo=TipoEsito.BREVETTO),
            cleaned_items=cleaned_brevetti,
            model_class=EsitoSpecialita,
            apply_fn=_apply_esito(TipoEsito.BREVETTO),
            impresa=impresa,
        )

    impresa.refresh_from_db()
    imp_data = _impresa_data(impresa)
    imp_data["numero"] = numero
    return 200, ImpresaResponseSchema(
        version=impresa.version,
        data=ImpresaSchema(
            **{k: v for k, v in imp_data.items() if k not in ("posti_azione", "specialita", "brevetti")},
            posti_azione=[PostoAzioneSchema(**p) for p in imp_data["posti_azione"]],
            specialita=[EsitoSpecialitaSchema(tipo="specialita", **e) for e in imp_data["specialita"]],
            brevetti=[EsitoSpecialitaSchema(tipo="brevetto", **e) for e in imp_data["brevetti"]],
        ),
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/diari/{diario_id}/missione
# ---------------------------------------------------------------------------

@router.put(
    "/{diario_id}/missione",
    response={200: MissioneResponseSchema, 400: ValidationErrorResponseSchema, 409: ConflictResponseSchema},
    summary="Aggiorna missione",
)
def put_missione(request, diario_id: int, payload: VersionedPutSchema):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from apps.api.schemas.diaries import MissioneSchema, PostoAzioneMissioneSchema
    from apps.diaries.models import Missione
    from apps.diaries.serialization import _date_field, _missione_data, _str_field

    d = _get_diario_write(diario_id)
    user = request.auth
    if not (is_staff_plancia(user) or puo_editare_diario(user, d)):
        raise HttpError(403, "Accesso non consentito")

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

    if errors:
        return 400, ValidationErrorResponseSchema(error="validation", errors=errors)

    with transaction.atomic():
        try:
            missione = Missione.objects.select_for_update().get(diario=d)
            if missione.version != payload.version:
                return 409, ConflictResponseSchema(server_version=missione.version)
        except Missione.DoesNotExist:
            if payload.version != 0:
                return 409, ConflictResponseSchema(server_version=0)
            missione = Missione(diario=d)

        _inizia_se_necessario(d)
        missione.titolo = titolo
        missione.data = data_missione
        missione.descrizione_svolgimento = descrizione
        missione.version = payload.version + 1
        missione.save()

    missione_data = _missione_data(missione)
    return 200, MissioneResponseSchema(
        version=missione.version,
        data=MissioneSchema(
            titolo=missione_data["titolo"],
            data=missione.data,
            descrizione_svolgimento=missione_data["descrizione_svolgimento"],
            posti_azione=[PostoAzioneMissioneSchema(**p) for p in missione_data["posti_azione"]],
        ),
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/diari/{diario_id}/relazione-finale
# ---------------------------------------------------------------------------

@router.put(
    "/{diario_id}/relazione-finale",
    response={200: RelazioneFinaleResponseSchema, 400: ValidationErrorResponseSchema},
    summary="Aggiorna relazione finale (solo Capo Reparto)",
)
def put_relazione_finale(request, diario_id: int, payload: RelazioneFinaleUpdateSchema):
    from django.core.exceptions import ValidationError

    from apps.api.schemas.diaries import RelazioneFinaleSchema
    from apps.diaries.models import RelazioneFinale
    from apps.diaries.serialization import (
        _apply_relazione_finale,
        _relazione_finale_data,
        _validate_relazione_finale,
    )

    d = _get_diario_write(diario_id)
    user = request.auth
    if not (is_staff_plancia(user) or puo_editare_relazione_finale(user, d)):
        raise HttpError(403, "Accesso non consentito")

    try:
        cleaned = _validate_relazione_finale(payload.data)
    except ValidationError as exc:
        return 400, ValidationErrorResponseSchema(error="validation", errors=exc.message_dict)

    rf, _ = RelazioneFinale.objects.get_or_create(diario=d)
    _apply_relazione_finale(rf, cleaned)
    rf.save()

    return 200, RelazioneFinaleResponseSchema(
        data=RelazioneFinaleSchema(**_relazione_finale_data(rf)),
    )
