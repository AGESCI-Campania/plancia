"""Google Drive: avvio OAuth, stato del collegamento, picker cartelle, cartelle dell'edizione.

Tutto riservato allo staff (Admin, Segreteria, Incaricati EG) come le viste web. La callback
OAuth resta la vista Django `/drive/oauth/callback/` (registrata presso Google) e reindirizza
alla SPA. Le chiamate a Google stanno in `apps.storage_drive.service` / `.oauth`.
"""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from ninja import Query, Router, Status
from ninja.errors import HttpError

from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.permissions import richiedi_staff
from apps.api.schemas.drive import (
    AccountDriveSchema,
    CartellaCreaInSchema,
    CartellaInfoSchema,
    CartellaSchema,
    DriveEdizioneInSchema,
    DriveEdizioneSchema,
    OAuthAvvioInSchema,
    OAuthUrlSchema,
    StatoDriveSchema,
)

logger = logging.getLogger(__name__)

router = Router(tags=["drive"])

_ERRORI = {403: ErroreSchema, 404: ErroreSchema}
_ERRORI_GOOGLE = {**_ERRORI, 422: ErroreValidazioneSchema, 502: ErroreSchema}


def _credenziali(account: str):
    from apps.storage_drive.models import DriveCredenziali

    try:
        return DriveCredenziali.objects.get(account_email=account)
    except DriveCredenziali.DoesNotExist:
        raise HttpError(404, "Account Drive non collegato.") from None


def _errore_google(exc: Exception) -> HttpError:
    logger.warning("Errore Google Drive: %s", exc)
    return HttpError(502, f"Errore di Google Drive: {exc}")


@router.post(
    "/oauth", response={200: OAuthUrlSchema, **_ERRORI, 422: ErroreSchema},
    summary="Avvia il collegamento OAuth a Google Drive",
)
def avvia_oauth(request, payload: OAuthAvvioInSchema | None = None):
    """Restituisce l'URL di autorizzazione Google (PKCE e state salvati in sessione).

    Al ritorno, la callback reindirizza a `/edizioni/<id>?drive=ok|errore` se è indicata
    un'edizione, altrimenti a `/impostazioni/drive?esito=ok|errore` (con `messaggio`).
    """
    from apps.editions.models import Edizione
    from apps.storage_drive.oauth import avvia_oauth_drive, oauth_configurato

    richiedi_staff(request.auth)
    edizione_id = payload.edizione_id if payload else None
    if edizione_id is not None:
        get_object_or_404(Edizione, pk=edizione_id)
    if not oauth_configurato():
        raise HttpError(422, "Client OAuth di Google non configurato sul server.")
    return OAuthUrlSchema(url=avvia_oauth_drive(request, edizione_id or ""))


@router.get("/stato", response={200: StatoDriveSchema, 403: ErroreSchema},
            summary="Stato del collegamento a Google Drive")
def stato(request):
    """Client OAuth configurato e account Drive collegati (nessun token esposto)."""
    from apps.storage_drive.models import DriveCredenziali
    from apps.storage_drive.oauth import oauth_configurato

    richiedi_staff(request.auth)
    return StatoDriveSchema(
        oauth_configurato=oauth_configurato(),
        account=[
            AccountDriveSchema(email=c.account_email, token_scaduto=c.scaduto,
                               aggiornato_at=c.aggiornato_at)
            for c in DriveCredenziali.objects.order_by("account_email")
        ],
    )


# ---------------------------------------------------------------------------
# Picker cartelle
# ---------------------------------------------------------------------------

@router.get("/cartelle", response={200: list[CartellaSchema], **_ERRORI_GOOGLE},
            summary="Cerca cartelle Drive dell'account")
def elenca_cartelle(request, account: str = Query(...), q: str = Query("")):
    """Prime 20 cartelle dell'account il cui nome contiene `q`."""
    from apps.storage_drive.service import elenca_cartelle as _elenca

    richiedi_staff(request.auth)
    cred = _credenziali(account)
    try:
        cartelle = _elenca(cred, q)
    except Exception as exc:
        raise _errore_google(exc) from exc
    return [CartellaSchema(id=c["id"], nome=c.get("name", "")) for c in cartelle]


@router.post("/cartelle", response={201: CartellaSchema, **_ERRORI_GOOGLE},
             summary="Crea una cartella Drive")
def crea_cartella(request, payload: CartellaCreaInSchema):
    from django.core.exceptions import ValidationError

    from apps.storage_drive.service import crea_cartella as _crea

    richiedi_staff(request.auth)
    nome = payload.nome.strip()
    if not nome:
        raise ValidationError({"nome": ["Il nome è obbligatorio."]})
    cred = _credenziali(payload.account)
    try:
        folder_id = _crea(cred, nome, payload.parent_id or None)
    except Exception as exc:
        raise _errore_google(exc) from exc
    return Status(201, CartellaSchema(id=folder_id, nome=nome))


@router.get("/cartelle/{folder_id}", response={200: CartellaInfoSchema, **_ERRORI_GOOGLE},
            summary="Nome e link di una cartella Drive")
def info_cartella(request, folder_id: str, account: str = Query(...)):
    from apps.storage_drive.service import info_cartella as _info

    richiedi_staff(request.auth)
    cred = _credenziali(account)
    try:
        info = _info(cred, folder_id)
    except Exception as exc:
        raise _errore_google(exc) from exc
    return CartellaInfoSchema(id=folder_id, nome=info["name"], url=info["url"])


# ---------------------------------------------------------------------------
# Cartelle dell'edizione
# ---------------------------------------------------------------------------

def _drive_edizione_schema(e) -> DriveEdizioneSchema:
    from apps.storage_drive.models import DriveCredenziali

    return DriveEdizioneSchema(
        edizione_id=e.pk,
        account=e.drive_oauth_account,
        account_collegato=bool(e.drive_oauth_account) and DriveCredenziali.objects.filter(
            account_email=e.drive_oauth_account).exists(),
        drive_folder_allegati_id=e.drive_folder_allegati_id,
        drive_folder_output_id=e.drive_folder_output_id,
        cartella_diario_format=e.cartella_diario_format,
        cartelle_configurate=e.cartelle_configurate,
    )


@router.get("/edizioni/{edizione_id}", response={200: DriveEdizioneSchema, **_ERRORI},
            summary="Configurazione Drive dell'edizione")
def drive_edizione(request, edizione_id: int):
    from apps.editions.models import Edizione

    richiedi_staff(request.auth)
    return _drive_edizione_schema(get_object_or_404(Edizione, pk=edizione_id))


@router.put(
    "/edizioni/{edizione_id}", response={200: DriveEdizioneSchema, **_ERRORI,
                                         422: ErroreValidazioneSchema},
    summary="Salva cartelle Drive e formato nome (poi bloccati)",
)
def salva_drive_edizione(request, edizione_id: int, payload: DriveEdizioneInSchema):
    """Quando cartella allegati, cartella output e formato sono tutti valorizzati la
    configurazione si blocca: ogni modifica successiva risponde 422."""
    from apps.editions.models import Edizione
    from apps.storage_drive.service import configura_cartelle_edizione

    richiedi_staff(request.auth)
    edizione = get_object_or_404(Edizione, pk=edizione_id)
    configura_cartelle_edizione(
        edizione, payload.drive_folder_allegati_id, payload.drive_folder_output_id,
        payload.cartella_diario_format,
    )
    return _drive_edizione_schema(edizione)
