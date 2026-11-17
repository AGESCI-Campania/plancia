# apps/api/routers/notifiche.py
"""Inviti: gestione (staff), inviti del Capo Reparto, reinvio, attivazione account (pubblica).

La logica sta in `apps.notifications.service` (condivisa con le viste web).
"""

import uuid

from django.shortcuts import get_object_or_404
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination, paginate
from ninja.responses import Status

from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.permissions import richiedi_ruolo, richiedi_staff
from apps.api.schemas.notifiche import (
    AttivaInvitoIn,
    AttivazioneSchema,
    EdizioneInvitiSchema,
    EsitoNotificaSchema,
    InviaInvitiDiarioIn,
    InviaInvitiEdizioneIn,
    InvitiCrpSchema,
    InvitoPubblicoSchema,
    InvitoSchema,
    PersonaInvitoSchema,
    ReinvioSchema,
    RiepilogoInvitiSchema,
    RigaInvitiCrpSchema,
    RigaInvitiSchema,
)

router = Router(tags=["notifiche"])

_ERRORI = {401: ErroreSchema, 403: ErroreSchema, 404: ErroreSchema, 422: ErroreValidazioneSchema}


# ---------------------------------------------------------------------------
# Conversioni
# ---------------------------------------------------------------------------

def _email_reale(email: str | None) -> str | None:
    return email if email and not email.endswith("@noemail.internal") else None


def _invito(inv) -> InvitoSchema | None:
    if inv is None:
        return None
    return InvitoSchema(
        id=inv.pk,
        ruolo_target=inv.ruolo_target,
        ruolo_target_display=inv.get_ruolo_target_display(),
        tipo=inv.tipo,
        stato=inv.stato,
        stato_display=inv.get_stato_display(),
        inviato_at=inv.inviato_at,
        attivato_at=inv.attivato_at,
        delivery_status=inv.delivery_status,
        delivery_status_display=inv.get_delivery_status_display(),
        delivery_error=inv.delivery_error,
        email_destinatario=_email_reale(inv.utente.email) or "",
    )


def _persona(socio) -> PersonaInvitoSchema | None:
    if socio is None:
        return None
    return PersonaInvitoSchema(
        socio_id=socio.pk, nome=socio.nome, cognome=socio.cognome,
        email=_email_reale(socio.email), provvisorio=bool(getattr(socio, "provvisorio", False)),
    )


def _edizione(ed) -> EdizioneInvitiSchema | None:
    return EdizioneInvitiSchema(id=ed.pk, anno=ed.anno, nome=str(ed)) if ed else None


# ---------------------------------------------------------------------------
# Gestione inviti (staff)
# ---------------------------------------------------------------------------

@router.get(
    "/inviti/riepilogo", response={200: RiepilogoInvitiSchema, **_ERRORI},
    summary="Riepilogo inviti dell'edizione attiva (contatori e filtri)",
)
def riepilogo_inviti(request):
    from apps.notifications import service
    from apps.siteconfig.models import BackendPosta, Impostazioni

    richiedi_staff(request.auth)
    edizione = service.edizione_inviti_attiva()
    etichetta = BackendPosta(Impostazioni.get().email_backend_massivo).label
    if not edizione:
        return RiepilogoInvitiSchema(edizione=None, contatori=None, zone=[], gruppi=[],
                                     backend_massivo_display=etichetta)
    diari = service.diari_con_ultimi_inviti(edizione)
    return RiepilogoInvitiSchema(
        edizione=_edizione(edizione),
        contatori=service.calcola_stato_inviti(diari),
        zone=sorted({d.squadriglia.reparto.gruppo.zona.nome for d in diari}),
        gruppi=sorted({d.squadriglia.reparto.gruppo.nome for d in diari}),
        backend_massivo_display=etichetta,
    )


class FiltriInviti(Schema):
    zona: str | None = None
    gruppo: str | None = None
    q: str | None = None  # cognome/nome di Capo Squadriglia o Capo Reparto


def _corrisponde(d, filtri: FiltriInviti) -> bool:
    gruppo = d.squadriglia.reparto.gruppo
    if filtri.zona and gruppo.zona.nome != filtri.zona:
        return False
    if filtri.gruppo and gruppo.nome != filtri.gruppo:
        return False
    if filtri.q:
        testo = " ".join(
            f"{s.cognome} {s.nome}" for s in (d.csq, d.crp) if s is not None
        ).lower()
        if filtri.q.strip().lower() not in testo:
            return False
    return True


@router.get(
    "/inviti", response={200: list[RigaInvitiSchema], **_ERRORI},
    summary="Inviti dell'edizione attiva, un diario per riga (filtri zona, gruppo, ricerca)",
)
@paginate(LimitOffsetPagination)
def lista_inviti(request, filtri: Query[FiltriInviti]):
    from apps.notifications import service
    from apps.notifications.models import StatoInvito

    richiedi_staff(request.auth)
    edizione = service.edizione_inviti_attiva()
    if not edizione:
        return []
    righe = []
    for d in service.diari_con_ultimi_inviti(edizione):
        if not _corrisponde(d, filtri):
            continue
        rep = d.squadriglia.reparto
        righe.append(RigaInvitiSchema(
            diario_id=d.pk,
            squadriglia=d.squadriglia.nome,
            reparto=rep.nome,
            gruppo=rep.gruppo.nome,
            zona=rep.gruppo.zona.nome,
            csq=_persona(d.csq),
            crp=_persona(d.crp),
            ultimo_invito_csq=_invito(d.ultimo_invito_csq),
            ultimo_invito_crp=_invito(d.ultimo_invito_crp),
            inviti_reinviabili=[i.pk for i in d.inviti.all() if i.stato == StatoInvito.INVIATO],
        ))
    return righe


@router.post(
    "/inviti/invia-edizione", response={202: EsitoNotificaSchema, **_ERRORI},
    summary="Invia gli inviti dell'edizione attiva ai Capi Reparto o ai Capi Squadriglia",
)
def invia_inviti_edizione(request, payload: InviaInvitiEdizioneIn):
    from apps.notifications import service

    richiedi_staff(request.auth)
    esito = service.avvia_invio_inviti_edizione(
        service.edizione_inviti_attiva(), payload.tipo, payload.backend
    )
    return Status(202, {"detail": esito})


@router.post(
    "/diari/{int:diario_id}/inviti", response={202: EsitoNotificaSchema, **_ERRORI},
    summary="Invia gli inviti mancanti di un diario (Capo Squadriglia e/o Capo Reparto)",
)
def invia_inviti_diario(request, diario_id: int, payload: InviaInvitiDiarioIn):
    from apps.diaries.models import Diario
    from apps.notifications import service

    richiedi_staff(request.auth)
    diario = get_object_or_404(Diario, pk=diario_id)
    service.accoda_inviti_diario(diario, list(payload.ruoli))
    return Status(202, {"detail": "Inviti accodati per l'invio."})


# ---------------------------------------------------------------------------
# Capo Reparto
# ---------------------------------------------------------------------------

@router.get(
    "/inviti/miei", response={200: InvitiCrpSchema, **_ERRORI},
    summary="Inviti ai Capi Squadriglia dei propri diari (Capo Reparto)",
)
def inviti_crp(request):
    from apps.accounts.models import Ruolo
    from apps.notifications import service
    from apps.notifications.models import StatoInvito

    richiedi_ruolo(request.auth, Ruolo.CRP)
    edizione = service.edizione_inviti_attiva()
    righe = [
        RigaInvitiCrpSchema(
            diario_id=d.pk,
            squadriglia=d.squadriglia.nome,
            reparto=str(d.squadriglia.reparto),
            csq=_persona(d.csq),
            ultimo_invito_csq=_invito(d.ultimo_invito_csq),
            reinviabile=bool(d.ultimo_invito_csq
                             and d.ultimo_invito_csq.stato != StatoInvito.ATTIVATO),
        )
        for d in service.diari_inviti_crp(edizione, request.auth.socio)
    ]
    return InvitiCrpSchema(edizione=_edizione(edizione), righe=righe)


@router.post(
    "/inviti/{int:invito_id}/reinvia", response={200: ReinvioSchema, **_ERRORI},
    summary="Reinvia un invito (nuovo link, il precedente scade)",
)
def reinvia(request, invito_id: int):
    from apps.notifications import service
    from apps.notifications.models import Invito

    user = request.auth
    richiedi_ruolo(user, "admin", "segreteria", "incaricato_eg", "crp")
    invito = get_object_or_404(Invito.objects.select_related("diario", "utente"), pk=invito_id)
    service.verifica_reinvio(user, invito)
    nuovo = service.reinvia_invito(invito)
    return {"detail": f"Invito reinviato a {_email_reale(invito.utente.email) or 'destinatario'}.",
            "invito": _invito(nuovo)}


# ---------------------------------------------------------------------------
# Attivazione account (pubblica)
# ---------------------------------------------------------------------------

def _invito_da_token(token: uuid.UUID):
    from apps.notifications.models import Invito

    return get_object_or_404(
        Invito.objects.select_related("utente__socio", "diario__squadriglia", "diario__edizione"),
        token=token,
    )


@router.get(
    "/inviti/{uuid:token}", auth=None,
    response={200: InvitoPubblicoSchema, 404: ErroreSchema},
    summary="Dati dell'invito per la pagina di attivazione (pubblico)",
)
def invito_pubblico(request, token: uuid.UUID):
    from django.core.exceptions import ValidationError

    from apps.notifications import service
    from apps.notifications.models import TipoInvito

    invito = _invito_da_token(token)
    try:
        service.controlla_invito_attivabile(invito)
        attivabile, messaggio = True, None
    except ValidationError as exc:
        attivabile, messaggio = False, exc.messages[0]
    return InvitoPubblicoSchema(
        tipo=invito.tipo,
        ruolo_target=invito.ruolo_target,
        ruolo_target_display=invito.get_ruolo_target_display(),
        stato=invito.stato,
        attivabile=attivabile,
        richiede_codice_socio=invito.tipo == TipoInvito.CODICE_SOCIO,
        messaggio=messaggio,
        squadriglia=invito.diario.squadriglia.nome if invito.diario else None,
        edizione=str(invito.diario.edizione) if invito.diario else None,
    )


@router.post(
    "/inviti/{uuid:token}/attiva", auth=None,
    response={200: AttivazioneSchema, 403: ErroreSchema, 404: ErroreSchema,
              422: ErroreValidazioneSchema},
    summary="Attiva l'account dall'invito ed effettua il login nella sessione (pubblico)",
)
def attiva_invito(request, token: uuid.UUID, payload: AttivaInvitoIn):
    from django.contrib.auth import login
    from django.db import transaction
    from ninja.utils import check_csrf

    from apps.notifications import service
    from apps.notifications.models import TipoInvito

    # Endpoint senza auth ma che crea una sessione: CSRF come per le altre POST della SPA.
    if check_csrf(request) is not None:
        raise HttpError(403, "Verifica CSRF non riuscita.")

    invito = _invito_da_token(token)
    with transaction.atomic():
        service.controlla_invito_attivabile(invito)
        if invito.tipo == TipoInvito.CODICE_SOCIO:
            service.conferma_codice_socio(invito, payload.codice_socio, payload.email)
        utente = service.completa_attivazione_invito(invito)

    if not service.login_da_invito_consentito(utente):
        return AttivazioneSchema(
            detail="Invito attivato: accedi con le tue credenziali.",
            ruolo=utente.ruolo, diario_id=invito.diario_id, login=False,
        )
    utente.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, utente)
    return AttivazioneSchema(
        detail=f"Benvenuto/a, {utente.get_full_name() or utente.email}!",
        ruolo=utente.ruolo,
        diario_id=invito.diario_id,
    )
