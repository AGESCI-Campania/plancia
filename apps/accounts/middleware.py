# apps/accounts/middleware.py
"""MFA obbligatoria sui percorsi Django rimasti (docs sez. 2, 12).

L'interfaccia è la SPA: la configurazione della MFA si fa lì (Profilo → Sicurezza, via
`/_allauth/`). Sull'API la stessa regola la applica `apps/api/auth.py` (403
`mfa_da_configurare`). Qui si coprono admin, proxy Mailpit/Flower e le altre viste Django:
chi deve configurare la MFA riceve 403 con una pagina statica che spiega cosa fare.
"""
from django.http import HttpResponse
from django.template.loader import get_template

from apps.accounts.adapters import mfa_da_configurare

# Percorsi esclusi: allauth headless (serve proprio a configurare la MFA), API (regola
# applicata da PlanciaAuth), callback dei provider, statici, healthcheck.
_PERCORSI_ESCLUSI = (
    "/_allauth/",
    "/api/v1/",
    "/accounts/",
    "/static/",
    "/media/",
    "/healthz/",
    "/anymail/",
)


class MFAEnforcementMiddleware:
    """403 agli utenti con ruolo che impone la MFA e senza MFA configurata.

    Le esenzioni (DEBUG, impersonazione, sessione aperta via Sestante) stanno in
    `adapters.mfa_da_configurare`, regola unica per web e API.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._deve_bloccare(request):
            return HttpResponse(get_template("403_mfa.html").render(), status=403)
        return self.get_response(request)

    def _deve_bloccare(self, request) -> bool:
        if request.path_info.startswith(_PERCORSI_ESCLUSI):
            return False
        return mfa_da_configurare(request, request.user)
