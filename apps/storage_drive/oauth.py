"""Flusso OAuth di Google Drive (PKCE): avvio dall'API, callback dalla vista Django.

L'avvio salva `state`, `code_verifier` e l'edizione in sessione e restituisce l'URL di
autorizzazione; la callback (vista Django su `/drive/oauth/callback/`, percorso registrato
presso Google) chiama `completa_oauth_drive` e poi reindirizza alla SPA.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass

from django.conf import settings

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_SESSION_STATE = "drive_oauth_state"
_SESSION_EDIZIONE = "drive_oauth_edizione"
_SESSION_VERIFIER = "drive_oauth_code_verifier"


class OAuthDriveErrore(Exception):
    """Errore nel completamento del flusso OAuth (sessione non valida, scambio fallito)."""


@dataclass
class EsitoOAuthDrive:
    email: str
    edizione_pk: str


def oauth_client_config() -> dict:
    return {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def oauth_configurato() -> bool:
    """True se client id e secret Google sono impostati."""
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def avvia_oauth_drive(request, edizione_pk: str | int | None = "") -> str:
    """Genera PKCE e state, li salva in sessione e restituisce l'URL di autorizzazione."""
    from google_auth_oauthlib.flow import Flow

    # PKCE (richiesto da Google per tutti i client OAuth da ottobre 2024)
    code_verifier = secrets.token_urlsafe(96)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    flow = Flow.from_client_config(
        oauth_client_config(),
        scopes=DRIVE_SCOPES,
        redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    request.session[_SESSION_STATE] = state
    request.session[_SESSION_EDIZIONE] = str(edizione_pk or "")
    request.session[_SESSION_VERIFIER] = code_verifier
    return auth_url


def edizione_in_sessione(request) -> str:
    """L'edizione per cui è stato avviato il flusso (letta senza consumarla)."""
    return str(request.session.get(_SESSION_EDIZIONE) or "")


def completa_oauth_drive(request) -> EsitoOAuthDrive:
    """Scambia il codice, salva `DriveCredenziali` e collega l'account all'edizione (se c'è).

    Solleva `OAuthDriveErrore` se la sessione non è valida o lo scambio con Google fallisce.
    """
    import os

    from django.utils import timezone
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build

    from apps.editions.models import Edizione
    from apps.storage_drive.models import DriveCredenziali

    state = request.session.pop(_SESSION_STATE, None)
    edizione_pk = str(request.session.pop(_SESSION_EDIZIONE, None) or "")
    code_verifier = request.session.pop(_SESSION_VERIFIER, None)

    if not state or state != request.GET.get("state"):
        raise OAuthDriveErrore("Sessione OAuth non valida. Riprova.")
    if request.GET.get("error"):
        raise OAuthDriveErrore("Autorizzazione a Google Drive negata.")

    # In dev il redirect URI è http: oauthlib richiede https salvo questa env var.
    # In produzione no: dietro Caddy la callback è https (SECURE_PROXY_SSL_HEADER).
    if settings.DEBUG:
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    try:
        flow = Flow.from_client_config(
            oauth_client_config(),
            scopes=DRIVE_SCOPES,
            state=state,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
        )
        flow.fetch_token(
            authorization_response=request.build_absolute_uri(),
            code_verifier=code_verifier,
        )
        creds = flow.credentials
        service = build("oauth2", "v2", credentials=creds)
        email = service.userinfo().get().execute().get("email", "")
    except Exception as exc:
        raise OAuthDriveErrore("Collegamento a Google Drive non riuscito. Riprova.") from exc

    expires_at = None
    if creds.expiry:
        expires_at = (
            timezone.make_aware(creds.expiry) if creds.expiry.tzinfo is None else creds.expiry
        )
    DriveCredenziali.objects.update_or_create(
        account_email=email,
        defaults={
            "access_token": creds.token,
            "refresh_token": creds.refresh_token or "",
            "expires_at": expires_at,
        },
    )

    if edizione_pk:
        ed = Edizione.objects.filter(pk=edizione_pk).first() if edizione_pk.isdigit() else None
        if ed is None:
            edizione_pk = ""
        else:
            ed.drive_oauth_account = email
            ed.save(update_fields=["drive_oauth_account"])
    return EsitoOAuthDrive(email=email, edizione_pk=edizione_pk)
