# apps/accounts/middleware.py
"""Middleware per l'enforcement della MFA sui ruoli privilegiati (docs sez. 2, 12)."""
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from apps.accounts.adapters import ruolo_richiede_mfa

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
        if settings.DEBUG or getattr(settings, "SKIP_MFA_ENFORCEMENT", False):
            return False
        user = request.user
        if not user.is_authenticated:
            return False
        # Durante l'impersonazione (hijack) non forzare: l'operatore reale ha già la MFA.
        if getattr(user, "is_hijacked", False):
            return False
        if not ruolo_richiede_mfa(user):
            return False
        if any(request.path_info.startswith(p) for p in _PERCORSI_ESCLUSI):
            return False
        # SSO Sestante: la MFA è garantita dall'IdP, non va richiesta di nuovo qui.
        from allauth.socialaccount.models import SocialAccount
        if SocialAccount.objects.filter(user=user, provider="sestante").exists():
            return False

        from allauth.mfa.utils import is_mfa_enabled
        return not is_mfa_enabled(user)
