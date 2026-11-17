# apps/api/auth.py
"""Auth backends per l'API REST.

Due client supportati:
- browser: cookie di sessione Django standard (request.user già valorizzato da AuthenticationMiddleware)
- app:     header X-Session-Token → chiave di sessione emessa da /_allauth/app/v1/auth/login
"""
from __future__ import annotations

from django.contrib.auth import SESSION_KEY
from ninja.security import APIKeyHeader, SessionAuth


class SessionTokenAuth(APIKeyHeader):
    """Auth per client app (es. app mobile): invia il session key nell'header X-Session-Token."""

    param_name = "X-Session-Token"
    openapi_description = (
        "Token di sessione restituito da POST /_allauth/app/v1/auth/login. "
        "Inviare nell'header X-Session-Token."
    )

    def authenticate(self, request, key: str | None):
        from allauth.headless import app_settings as headless_settings

        from apps.accounts.models import User

        if not key:
            return None
        strategy = headless_settings.TOKEN_STRATEGY
        session = strategy.lookup_session(key)
        if session is None:
            return None
        try:
            user_id = session[SESSION_KEY]
            user = User.objects.get(pk=user_id)
        except (KeyError, User.DoesNotExist):
            return None
        if not user.is_active:
            return None
        # Inietta la sessione nella request così il resto del middleware la vede.
        request.session = session
        return user


# Con la MFA obbligatoria e non ancora configurata l'utente può usare solo il proprio
# profilo (`/me…`): il resto dell'API risponde 403 con `mfa_da_configurare` finché non
# configura la MFA (che passa da allauth headless, fuori da /api/v1). Stesse esenzioni di
# MFAEnforcementMiddleware, che non agisce su /api/v1/.
_PERCORSI_SENZA_MFA = ("/api/v1/me",)


class MfaDaConfigurare(Exception):
    """Risposta 403 con `mfa_da_configurare: true` (gestore in `apps.api.errors`)."""


def _controlla_mfa(request, user):
    from apps.accounts.adapters import mfa_da_configurare

    if (
        user is not None
        and not request.path_info.startswith(_PERCORSI_SENZA_MFA)
        and mfa_da_configurare(request, user)
    ):
        raise MfaDaConfigurare
    return user


class SessioneDjangoConMfa(SessionAuth):
    """Cookie di sessione (SPA), con l'obbligo di MFA."""

    def authenticate(self, request, key):
        return _controlla_mfa(request, super().authenticate(request, key))


class SessionTokenConMfa(SessionTokenAuth):
    """X-Session-Token (app mobile), con l'obbligo di MFA."""

    def authenticate(self, request, key):
        return _controlla_mfa(request, super().authenticate(request, key))


# Lista usata in NinjaAPI(auth=[...]): prima tenta cookie, poi header.
# Se uno dei due funziona, request.auth viene impostato all'utente.
plancia_auth = [SessioneDjangoConMfa(), SessionTokenConMfa()]
