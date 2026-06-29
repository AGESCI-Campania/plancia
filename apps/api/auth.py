# apps/api/auth.py
"""Auth backends per l'API REST.

Due client supportati:
- browser: cookie di sessione Django standard (request.user già valorizzato da AuthenticationMiddleware)
- app:     header X-Session-Token → chiave di sessione emessa da /_allauth/app/v1/auth/login
"""
from __future__ import annotations

from django.contrib.auth import SESSION_KEY
from ninja.security import APIKeyHeader, django_auth


class SessionTokenAuth(APIKeyHeader):
    """Auth per client app (es. app mobile): invia il session key nell'header X-Session-Token."""

    param_name = "X-Session-Token"
    openapi_description = (
        "Token di sessione restituito da POST /_allauth/app/v1/auth/login. "
        "Inviare nell'header X-Session-Token."
    )

    def authenticate(self, request, key: str):
        from allauth.headless import app_settings as headless_settings

        from apps.accounts.models import User

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


# Lista usata in NinjaAPI(auth=[...]): prima tenta cookie, poi header.
# Se uno dei due funziona, request.auth viene impostato all'utente.
plancia_auth = [django_auth, SessionTokenAuth()]
