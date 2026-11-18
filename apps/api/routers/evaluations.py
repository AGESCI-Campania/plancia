# apps/api/routers/evaluations.py
"""Endpoint API per transizioni FSM e azioni di valutazione (montato su `/diari`).

Permessi fine-grained e stato: sempre `apps.evaluations.actions` (le eccezioni diventano
403/422 tramite i gestori globali). Qui il controllo grossolano sul ruolo attivo e la
visibilità del diario (`diari_visibili`).
"""
from ninja import Router, Status
from ninja.errors import HttpError

from apps.accounts.models import Ruolo
from apps.api.permissions import puo_vedere_diario, richiedi_ruolo
from apps.api.schemas.evaluations import (
    ActionErrorSchema,
    AssegnaPGVBodySchema,
    AssegnazionePGVApiSchema,
    AzioniValutazioneSchema,
    ConfermaBodySchema,
    DiarioStatoSchema,
    ValutaBodySchema,
    ValutazioneApiSchema,
)

router = Router(tags=["valutazione"])

_AZIONI_FSM = ("csq-invia", "invia", "riapri")

#: Controllo grossolano dei ruoli; quello fine sta in `apps/evaluations/actions.py`.
_RUOLI_VALUTAZIONE_DIRETTA = (Ruolo.INCARICATO_EG, Ruolo.ADMIN, Ruolo.SEGRETERIA)
_RUOLI_CONFERMA = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

_ERRORI = {403: ActionErrorSchema, 404: ActionErrorSchema, 422: ActionErrorSchema}


def _get_diario(diario_id: int):
    from apps.diaries.models import Diario
    try:
        return Diario.objects.select_related(
            "edizione", "squadriglia", "csq", "crp"
        ).get(pk=diario_id)
    except Diario.DoesNotExist:
        raise HttpError(404, "Diario non trovato") from None


def _ha_ruolo(user, ruoli) -> bool:
    return bool(user.is_superuser or user.ruolo in ruoli)


def _nome(u) -> str | None:
    return u.nome_completo if u else None


def _azioni(val, user) -> AzioniValutazioneSchema:
    """Azioni proponibili all'utente (indicative: il backend ricontrolla sempre)."""
    from apps.diaries.models import StatoDiario
    from apps.evaluations.models import StatoValutazione

    d = val.diario
    pubblicata = val.pubblicata
    conferma = _ha_ruolo(user, _RUOLI_CONFERMA)
    in_revisione = val.stato == StatoValutazione.IN_REVISIONE
    return AzioniValutazioneSchema(
        puo_valutare_direttamente=_ha_ruolo(user, _RUOLI_VALUTAZIONE_DIRETTA) and not pubblicata
        and d.stato in (StatoDiario.INVIATO, StatoDiario.IN_VALUTAZIONE, StatoDiario.IN_REVISIONE),
        # La proposta porta il diario IN_REVISIONE: ammessa solo da IN_VALUTAZIONE/IN_REVISIONE
        # (`proponi_pgv` non avvia la valutazione di un diario solo inviato).
        puo_proporre=user.ruolo == Ruolo.PGV and not pubblicata
        and d.stato in (StatoDiario.IN_VALUTAZIONE, StatoDiario.IN_REVISIONE),
        puo_confermare=conferma and in_revisione,
        puo_rigettare=conferma and in_revisione,
        puo_modificare=conferma and bool(val.esito) and not pubblicata,
        puo_pubblicare=conferma and bool(val.esito) and not pubblicata,
        puo_assegnare_pgv=_ha_ruolo(user, _RUOLI_VALUTAZIONE_DIRETTA),
    )


def _verifica_visibilita(user, d) -> None:
    """Mai al Capo Squadriglia; al Capo Reparto solo dopo la pubblicazione; per gli altri
    la visibilità del diario (Pattuglia GV: solo i diari assegnati)."""
    if user.ruolo == Ruolo.CSQ and not user.is_superuser:
        raise HttpError(403, "Valutazione non ancora pubblicata.")
    if not puo_vedere_diario(user, d):
        raise HttpError(403, "Non hai accesso a questo diario.")
    if user.ruolo == Ruolo.CRP and not user.is_superuser and not d.pubblicato:
        raise HttpError(403, "Valutazione non ancora pubblicata.")


def _val_schema(val, user=None) -> ValutazioneApiSchema:
    return ValutazioneApiSchema(
        esito=val.esito,
        esito_display=val.get_esito_display() if val.esito else None,
        stato=val.stato,
        note=val.note,
        pubblicata=val.pubblicata,
        assegnazioni=[
            AssegnazionePGVApiSchema(
                pgv_pk=a.pgv_id, pgv_nome=a.pgv.nome_completo,
                pgv_email=a.pgv.email,
            )
            for a in val.assegnazioni_pgv.select_related("pgv")
        ],
        stato_display=val.get_stato_display(),
        proposta_esito=val.proposta_esito,
        proposta_esito_display=val.get_proposta_esito_display() if val.proposta_esito else None,
        valutatore=_nome(val.valutatore),
        confermata_da=_nome(val.confermata_da),
        aggiornata_at=val.aggiornata_at,
        diario_stato=val.diario.stato,
        azioni=_azioni(val, user) if user is not None else None,
    )


def _risposta(diario_id: int, user) -> ValutazioneApiSchema:
    from apps.evaluations.models import Valutazione

    val = Valutazione.objects.select_related("diario", "valutatore", "confermata_da").get(
        diario_id=diario_id
    )
    return _val_schema(val, user)


# ---------------------------------------------------------------------------
# POST /api/v1/diari/{diario_id}/azioni/{azione}
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/azioni/{azione}",
    response={200: DiarioStatoSchema, **_ERRORI},
    summary="Esegui transizione FSM sul diario",
)
def esegui_azione(request, diario_id: int, azione: str):
    from apps.evaluations.actions import csq_invia, invia, riapri

    if azione not in _AZIONI_FSM:
        raise HttpError(404, f"Azione non valida. Valori ammessi: {', '.join(_AZIONI_FSM)}")

    d = _get_diario(diario_id)
    user = request.auth
    if azione == "csq-invia":
        csq_invia(d, user)
    elif azione == "invia":
        invia(d, user)
    elif azione == "riapri":
        riapri(d, user)

    d.refresh_from_db()
    return Status(200, DiarioStatoSchema(stato=d.stato, stato_display=d.get_stato_display()))


# ---------------------------------------------------------------------------
# GET /api/v1/diari/{diario_id}/valutazione
# ---------------------------------------------------------------------------

@router.get(
    "/{diario_id}/valutazione",
    response={200: ValutazioneApiSchema, **_ERRORI},
    summary="Dettaglio valutazione",
)
def get_valutazione(request, diario_id: int):
    """Mai al Capo Squadriglia; al Capo Reparto solo dopo la pubblicazione; alla Pattuglia GV
    solo per i diari assegnati; lo staff vede sempre. 404 se non c'è ancora una valutazione."""
    from apps.evaluations.models import Valutazione

    d = _get_diario(diario_id)
    user = request.auth
    _verifica_visibilita(user, d)

    try:
        return Status(200, _risposta(d.pk, user))
    except Valutazione.DoesNotExist:
        raise HttpError(404, "Nessuna valutazione per questo diario") from None


@router.get(
    "/{diario_id}/valutazione/azioni",
    response={200: AzioniValutazioneSchema, **_ERRORI},
    summary="Azioni di valutazione proponibili (anche prima che la valutazione esista)",
)
def get_azioni_valutazione(request, diario_id: int):
    """Come `azioni` del dettaglio, ma risponde anche quando il diario non ha ancora una
    valutazione (il dettaglio dà 404): la pagina può proporre la prima valutazione o
    l'assegnazione alla Pattuglia GV. Stessa visibilità del dettaglio; non crea nulla."""
    from apps.evaluations.models import Valutazione

    d = _get_diario(diario_id)
    _verifica_visibilita(request.auth, d)
    val = Valutazione.objects.filter(diario=d).first() or Valutazione(diario=d)
    return Status(200, _azioni(val, request.auth))


# ---------------------------------------------------------------------------
# Azioni di valutazione
# ---------------------------------------------------------------------------

@router.post(
    "/{diario_id}/valutazione/assegna-pgv",
    response={200: ValutazioneApiSchema, **_ERRORI},
    summary="Assegna un membro della Pattuglia GV al diario",
)
def assegna_pgv_api(request, diario_id: int, payload: AssegnaPGVBodySchema):
    from apps.accounts.models import User
    from apps.evaluations.actions import assegna_pgv

    richiedi_ruolo(request.auth, *_RUOLI_VALUTAZIONE_DIRETTA)
    d = _get_diario(diario_id)
    try:
        pgv = User.objects.get(pk=payload.pgv_pk)
    except User.DoesNotExist:
        raise HttpError(404, "Utente non trovato") from None

    assegna_pgv(d, pgv, request.auth)
    return Status(200, _risposta(d.pk, request.auth))


@router.post(
    "/{diario_id}/valutazione/valuta",
    response={200: ValutazioneApiSchema, **_ERRORI},
    summary="Valuta direttamente (Incaricato EG / Admin / Segreteria)",
)
def valuta_api(request, diario_id: int, payload: ValutaBodySchema):
    """Accetta anche un diario `inviato` (avvia la valutazione) e sovrascrive una proposta
    della Pattuglia GV in revisione."""
    from apps.evaluations.actions import valuta_direttamente

    richiedi_ruolo(request.auth, *_RUOLI_VALUTAZIONE_DIRETTA)
    d = _get_diario(diario_id)
    valuta_direttamente(d, payload.esito, payload.note, request.auth)
    return Status(200, _risposta(d.pk, request.auth))


@router.post(
    "/{diario_id}/valutazione/proposta",
    response={200: ValutazioneApiSchema, **_ERRORI},
    summary="Proponi valutazione (Pattuglia GV)",
)
def proposta_api(request, diario_id: int, payload: ValutaBodySchema):
    """Solo Approvata / Non approvata, solo sui diari assegnati; va confermata dall'Incaricato."""
    from apps.evaluations.actions import proponi_pgv

    richiedi_ruolo(request.auth, Ruolo.PGV)
    d = _get_diario(diario_id)
    proponi_pgv(d, payload.esito, payload.note, request.auth)
    return Status(200, _risposta(d.pk, request.auth))


@router.post(
    "/{diario_id}/valutazione/conferma",
    response={200: ValutazioneApiSchema, **_ERRORI},
    summary="Conferma la proposta della Pattuglia GV (Incaricato EG / Admin)",
)
def conferma_api(request, diario_id: int, payload: ConfermaBodySchema):
    from apps.evaluations.actions import conferma_proposta

    richiedi_ruolo(request.auth, *_RUOLI_CONFERMA)
    d = _get_diario(diario_id)
    conferma_proposta(d, payload.note, request.auth)
    return Status(200, _risposta(d.pk, request.auth))


@router.post(
    "/{diario_id}/valutazione/rigetta",
    response={200: ValutazioneApiSchema, **_ERRORI},
    summary="Rigetta la proposta della Pattuglia GV (Incaricato EG / Admin)",
)
def rigetta_api(request, diario_id: int):
    from apps.evaluations.actions import rigetta_proposta

    richiedi_ruolo(request.auth, *_RUOLI_CONFERMA)
    d = _get_diario(diario_id)
    rigetta_proposta(d, request.auth)
    return Status(200, _risposta(d.pk, request.auth))


@router.post(
    "/{diario_id}/valutazione/modifica",
    response={200: ValutazioneApiSchema, **_ERRORI},
    summary="Modifica esito prima della pubblicazione (Incaricato EG / Admin)",
)
def modifica_api(request, diario_id: int, payload: ValutaBodySchema):
    from apps.evaluations.actions import modifica_valutazione

    richiedi_ruolo(request.auth, *_RUOLI_CONFERMA)
    d = _get_diario(diario_id)
    modifica_valutazione(d, payload.esito, payload.note, request.auth)
    return Status(200, _risposta(d.pk, request.auth))


@router.post(
    "/{diario_id}/valutazione/pubblica",
    response={200: DiarioStatoSchema, **_ERRORI},
    summary="Pubblica esito del diario (Incaricato EG / Admin)",
)
def pubblica_api(request, diario_id: int):
    from apps.evaluations.actions import pubblica_esito

    richiedi_ruolo(request.auth, *_RUOLI_CONFERMA)
    d = _get_diario(diario_id)
    pubblica_esito(d, request.auth)
    d.refresh_from_db()
    return Status(200, DiarioStatoSchema(stato=d.stato, stato_display=d.get_stato_display()))
