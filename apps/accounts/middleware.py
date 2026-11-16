# apps/accounts/middleware.py
"""Middleware per l'enforcement della MFA sui ruoli privilegiati (docs sez. 2, 12)."""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from apps.accounts.adapters import mfa_da_configurare

# URL con prefisso esclusi dall'enforcement: MFA setup, login/logout, assets, API.
_PERCORSI_ESCLUSI = (
    "/accounts/",   # login, logout, password, MFA setup
    "/_allauth/",   # allauth headless API
    "/api/v1/",     # REST API (auth via X-Session-Token, non redirect)
    "/static/",
    "/media/",
    "/favicon.ico",
)


class MFAEnforcementMiddleware:
    """Reindirizza gli utenti privilegiati senza TOTP alla pagina di attivazione MFA.

    Non agisce durante le sessioni di impersonazione (django-hijack): l'operatore
    reale ha già superato la propria MFA. Vedi docs sez. 2 e 12.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._deve_forzare_setup(request):
            messages.warning(
                request,
                "Il tuo ruolo richiede l'autenticazione a due fattori. "
                "Configura l'app Authenticator per continuare.",
            )
            return redirect(reverse("mfa_activate_totp"))
        return self.get_response(request)

    def _deve_forzare_setup(self, request) -> bool:
        if any(request.path_info.startswith(p) for p in _PERCORSI_ESCLUSI):
            return False
        return mfa_da_configurare(request, request.user)
