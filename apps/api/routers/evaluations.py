# apps/api/routers/evaluations.py
"""Endpoint API per transizioni FSM e azioni di valutazione."""
from ninja import Router
from ninja.errors import HttpError

from apps.api.schemas.evaluations import (
    ActionErrorSchema,
    AssegnaPGVBodySchema,
    ConfermaBodySchema,
    DiarioStatoSchema,
    ValutaBodySchema,
    ValutazioneApiSchema,
)

router = Router(tags=["valutazione"])

_AZIONI_FSM = ("csq-invia", "invia", "riapri")


def _get_diario(diario_id: int):
    from apps.diaries.models import Diario
    try:
        return Diario.objects.select_related(
            "edizione", "squadriglia", "csq", "crp"
        ).get(pk=diario_id)
    except Diario.DoesNotExist:
        raise HttpError(404, "Diario non trovato") from None


def _val_schema(val) -> ValutazioneApiSchema:
    return ValutazioneApiSchema(
        esito=val.esito,
        esito_display=val.get_esito_display() if val.esito else None,
        stato=val.stato,
        note=val.note,
        pubblicata=val.pubblicata,
        assegnazioni=[
            {"pgv_pk": a.pgv_id, "pgv_nome": a.pgv.get_full_name() or a.pgv.email, "pgv_email": a.pgv.email}
            for a in val.assegnazioni_pgv.select_related("pgv")
        ],
    )


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/azioni/{azione}
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/azioni/{azione}",
    response={200: DiarioStatoSchema, 403: ActionErrorSchema, 422: ActionErrorSchema},
    summary="Esegui transizione FSM sul diario",
)
def esegui_azione(request, diario_id: int, azione: str):
    from apps.evaluations.actions import (
        PermessoNegato,
        StatoNonValido,
        csq_invia,
        invia,
        riapri,
    )

    if azione not in _AZIONI_FSM:
        raise HttpError(404, f"Azione non valida. Valori ammessi: {', '.join(_AZIONI_FSM)}")

    d = _get_diario(diario_id)
    user = request.auth

    try:
        if azione == "csq-invia":
            csq_invia(d, user)
        elif azione == "invia":
            invia(d, user)
        elif azione == "riapri":
            riapri(d, user)
    except PermessoNegato as e:
        return 403, ActionErrorSchema(detail=str(e))
    except StatoNonValido as e:
        return 422, ActionErrorSchema(detail=str(e))

    d.refresh_from_db()
    return 200, DiarioStatoSchema(stato=d.stato, stato_display=d.get_stato_display())


# ---------------------------------------------------------------------------
# GET /api/v1/diari/{diario_id}/valutazione
# ---------------------------------------------------------------------------

@router.get(
    "/{diario_id}/valutazione",
    response={200: ValutazioneApiSchema, 403: ActionErrorSchema},
    summary="Dettaglio valutazione",
)
def get_valutazione(request, diario_id: int):
    from apps.api.permissions import puo_vedere_valutazione
    from apps.evaluations.models import Valutazione

    d = _get_diario(diario_id)
    user = request.auth

    if user.ruolo == "csq" and not puo_vedere_valutazione(user, d):
        return 403, ActionErrorSchema(detail="Valutazione non ancora pubblicata.")

    try:
        val = d.valutazione
    except Valutazione.DoesNotExist:
        raise HttpError(404, "Nessuna valutazione per questo diario") from None

    if user.ruolo == "pgv" and not val.assegnazioni_pgv.filter(pgv=user).exists():
        return 403, ActionErrorSchema(detail="Non sei assegnato a questo diario.")

    return 200, _val_schema(val)


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/valutazione/assegna-pgv
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/valutazione/assegna-pgv",
    response={200: ValutazioneApiSchema, 403: ActionErrorSchema, 422: ActionErrorSchema},
    summary="Assegna un membro PGV al diario",
)
def assegna_pgv_api(request, diario_id: int, payload: AssegnaPGVBodySchema):
    from apps.accounts.models import User
    from apps.evaluations.actions import (
        PermessoNegato,
        StatoNonValido,
        assegna_pgv,
    )

    d = _get_diario(diario_id)
    try:
        pgv = User.objects.get(pk=payload.pgv_pk)
    except User.DoesNotExist:
        raise HttpError(404, "Utente non trovato") from None

    try:
        _, val = assegna_pgv(d, pgv, request.auth)
    except PermessoNegato as e:
        return 403, ActionErrorSchema(detail=str(e))
    except StatoNonValido as e:
        return 422, ActionErrorSchema(detail=str(e))

    return 200, _val_schema(val)


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/valutazione/valuta
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/valutazione/valuta",
    response={200: ValutazioneApiSchema, 403: ActionErrorSchema, 422: ActionErrorSchema},
    summary="Valuta direttamente (Incaricato EG / Admin / Segreteria)",
)
def valuta_api(request, diario_id: int, payload: ValutaBodySchema):
    from apps.evaluations.actions import PermessoNegato, StatoNonValido, valuta_direttamente

    d = _get_diario(diario_id)
    try:
        val = valuta_direttamente(d, payload.esito, payload.note, request.auth)
    except PermessoNegato as e:
        return 403, ActionErrorSchema(detail=str(e))
    except StatoNonValido as e:
        return 422, ActionErrorSchema(detail=str(e))

    return 200, _val_schema(val)


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/valutazione/proposta
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/valutazione/proposta",
    response={200: ValutazioneApiSchema, 403: ActionErrorSchema, 422: ActionErrorSchema},
    summary="Proponi valutazione (Pattuglia GV)",
)
def proposta_api(request, diario_id: int, payload: ValutaBodySchema):
    from apps.evaluations.actions import PermessoNegato, StatoNonValido, proponi_pgv

    d = _get_diario(diario_id)
    try:
        val = proponi_pgv(d, payload.esito, payload.note, request.auth)
    except PermessoNegato as e:
        return 403, ActionErrorSchema(detail=str(e))
    except StatoNonValido as e:
        return 422, ActionErrorSchema(detail=str(e))

    return 200, _val_schema(val)


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/valutazione/conferma
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/valutazione/conferma",
    response={200: ValutazioneApiSchema, 403: ActionErrorSchema, 422: ActionErrorSchema},
    summary="Conferma proposta PGV (Incaricato EG / Admin)",
)
def conferma_api(request, diario_id: int, payload: ConfermaBodySchema):
    from apps.evaluations.actions import PermessoNegato, StatoNonValido, conferma_proposta

    d = _get_diario(diario_id)
    try:
        val = conferma_proposta(d, payload.note, request.auth)
    except PermessoNegato as e:
        return 403, ActionErrorSchema(detail=str(e))
    except StatoNonValido as e:
        return 422, ActionErrorSchema(detail=str(e))

    return 200, _val_schema(val)


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/valutazione/rigetta
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/valutazione/rigetta",
    response={200: ValutazioneApiSchema, 403: ActionErrorSchema, 422: ActionErrorSchema},
    summary="Rigetta proposta PGV (Incaricato EG / Admin)",
)
def rigetta_api(request, diario_id: int):
    from apps.evaluations.actions import PermessoNegato, StatoNonValido, rigetta_proposta

    d = _get_diario(diario_id)
    try:
        val = rigetta_proposta(d, request.auth)
    except PermessoNegato as e:
        return 403, ActionErrorSchema(detail=str(e))
    except StatoNonValido as e:
        return 422, ActionErrorSchema(detail=str(e))

    return 200, _val_schema(val)


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/valutazione/modifica
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/valutazione/modifica",
    response={200: ValutazioneApiSchema, 403: ActionErrorSchema, 422: ActionErrorSchema},
    summary="Modifica esito prima della pubblicazione (Incaricato EG / Admin)",
)
def modifica_api(request, diario_id: int, payload: ValutaBodySchema):
    from apps.evaluations.actions import PermessoNegato, StatoNonValido, modifica_valutazione

    d = _get_diario(diario_id)
    try:
        val = modifica_valutazione(d, payload.esito, payload.note, request.auth)
    except PermessoNegato as e:
        return 403, ActionErrorSchema(detail=str(e))
    except StatoNonValido as e:
        return 422, ActionErrorSchema(detail=str(e))

    return 200, _val_schema(val)


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/valutazione/pubblica
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/valutazione/pubblica",
    response={200: DiarioStatoSchema, 403: ActionErrorSchema, 422: ActionErrorSchema},
    summary="Pubblica esito del diario (Incaricato EG / Admin)",
)
def pubblica_api(request, diario_id: int):
    from apps.evaluations.actions import PermessoNegato, StatoNonValido, pubblica_esito

    d = _get_diario(diario_id)
    try:
        pubblica_esito(d, request.auth)
    except PermessoNegato as e:
        return 403, ActionErrorSchema(detail=str(e))
    except StatoNonValido as e:
        return 422, ActionErrorSchema(detail=str(e))

    d.refresh_from_db()
    return 200, DiarioStatoSchema(stato=d.stato, stato_display=d.get_stato_display())
