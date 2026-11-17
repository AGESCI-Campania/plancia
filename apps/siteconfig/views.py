# apps/siteconfig/views.py
"""Viste Django rimaste dopo il passaggio alla SPA: callback OAuth Gmail SMTP e proxy
Mailpit/Flower (solo Admin). Tutto il resto delle impostazioni è in `/api/v1/impostazioni`."""
from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.csp import CSP
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csp import csp_override
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import Ruolo
from apps.siteconfig import services

logger = logging.getLogger(__name__)

# Pagina della SPA a cui torna la callback Gmail SMTP.
SPA_IMPOSTAZIONI_EMAIL = "/impostazioni/email"

# CSP dei proxy Mailpit/Flower (solo Admin): interfacce di terzi con script e stili inline e
# anteprime delle email in iframe; resta vietato l'incorporamento in altri siti.
CSP_STRUMENTI: dict[str, list[str]] = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.UNSAFE_INLINE, CSP.UNSAFE_EVAL],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:", "blob:", "https:"],
    "font-src": [CSP.SELF, "data:"],
    "connect-src": [CSP.SELF],
    "frame-src": [CSP.SELF, "blob:", "data:"],
    "object-src": [CSP.NONE],
    "frame-ancestors": [CSP.SELF],
}


class GmailSMTPOAuthCallbackView(View):
    """Callback OAuth Gmail SMTP: scambia il codice, salva GmailSMTPCredenziali, torna alla SPA.

    Resta sullo stesso percorso (registrato presso Google) e rimanda a
    `/impostazioni/email?esito=ok|errore&messaggio=...`.
    """

    def get(self, request):
        try:
            email = services.completa_oauth_gmail(
                request.session, request.GET.get("state"), request.build_absolute_uri()
            )
        except ValidationError as exc:
            esito, testo = "errore", exc.messages[0]
        except Exception as exc:  # errore di Google (consenso negato, codice non valido, …)
            logger.exception("Callback Gmail SMTP OAuth fallita")
            esito, testo = "errore", f"Collegamento Gmail non riuscito: {exc}"
        else:
            esito, testo = "ok", f"Account Gmail {email} collegato per SMTP OAuth."
        return redirect(f"{SPA_IMPOSTAZIONI_EMAIL}?{urlencode({'esito': esito, 'messaggio': testo})}")


def _solo_admin(request) -> HttpResponse | None:
    """Accesso ai proxy: anonimi alla pagina di accesso della SPA, non Admin 403.

    `MFAEnforcementMiddleware` ha già risposto 403 a chi deve configurare la MFA.
    """
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?{urlencode({'next': request.get_full_path()})}")
    if not (request.user.ruolo == Ruolo.ADMIN or request.user.is_superuser):
        raise PermissionDenied
    return None


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(csp_override(CSP_STRUMENTI), name="dispatch")
@method_decorator(xframe_options_sameorigin, name="dispatch")  # anteprime in iframe
class FlowerProxyView(View):
    """Proxy verso Flower (dashboard Celery) accessibile su /celery/.

    Solo Admin. Flower deve essere avviato con il profilo 'flower':
      COMPOSE_PROFILES=flower in .env, poi docker compose up -d
    """

    def dispatch(self, request, *args, **kwargs):
        return _solo_admin(request) or super().dispatch(request, *args, **kwargs)

    def get(self, request, path=""):
        return self._proxy(request, path)

    def post(self, request, path=""):
        return self._proxy(request, path)

    def _proxy(self, request, path):
        import urllib.error
        import urllib.request
        from urllib.parse import urlencode

        flower_base = getattr(settings, "FLOWER_INTERNAL_URL", "http://flower:5555").rstrip("/")
        target_path = f"/celery/{path}" if path else "/celery/"
        target_url = flower_base + target_path
        if request.GET:
            target_url += "?" + urlencode(request.GET)

        headers = {
            # Non passiamo Accept-Encoding: urllib non decomprime gzip e servirebbe
            # dati binari al browser invece di JSON/HTML leggibile.
            "Accept-Encoding": "identity",
        }
        for name in ("Accept", "X-Requested-With", "Content-Type"):
            if name in request.headers:
                headers[name] = request.headers[name]

        body = request.body if request.method in ("POST", "PUT", "PATCH") else None
        try:
            req = urllib.request.Request(target_url, data=body, headers=headers, method=request.method)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                content_type = resp.headers.get("Content-Type", "text/html")
                return HttpResponse(content, status=resp.status, content_type=content_type)
        except urllib.error.HTTPError as e:
            return HttpResponse(e.read(), status=e.code)
        except Exception as e:
            return HttpResponse(
                "<h1>Flower non raggiungibile</h1>"
                f"<pre>{e}</pre>"
                "<p>Avvia Flower con il profilo <code>flower</code>:<br>"
                "<code>COMPOSE_PROFILES=flower in .env, poi docker compose up -d</code></p>",
                status=503,
                content_type="text/html",
            )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(csp_override(CSP_STRUMENTI), name="dispatch")
@method_decorator(xframe_options_sameorigin, name="dispatch")  # anteprime in iframe
class MailpitProxyView(View):
    """Proxy verso Mailpit per il debug delle email in produzione.

    Accessibile su /mailadmin/ solo per utenti staff. Richiede che Mailpit sia
    avviato con --ui-web-path /mailadmin e raggiungibile all'URL MAILPIT_INTERNAL_URL.
    csrf_exempt: l'autenticazione è gestita da dispatch(); le richieste Mailpit
    (PUT/PATCH per mark-as-read, DELETE, ecc.) non portano il token Django.
    """

    def dispatch(self, request, *args, **kwargs):
        return _solo_admin(request) or super().dispatch(request, *args, **kwargs)

    def get(self, request, path=""):
        return self._proxy(request, path)

    def post(self, request, path=""):
        return self._proxy(request, path)

    def put(self, request, path=""):
        return self._proxy(request, path)

    def patch(self, request, path=""):
        return self._proxy(request, path)

    def delete(self, request, path=""):
        return self._proxy(request, path)

    def _proxy(self, request, path):
        import urllib.error
        import urllib.request
        from urllib.parse import urlencode

        mailpit_base = getattr(settings, "MAILPIT_INTERNAL_URL", "http://mailpit:8025").rstrip("/")
        target_path = f"/mailadmin/{path}".rstrip("/") or "/mailadmin/"
        target_url = mailpit_base + target_path
        if request.GET:
            target_url += "?" + urlencode(request.GET)

        headers = {}
        for name in ("Content-Type", "Accept", "X-Requested-With"):
            if name in request.headers:
                headers[name] = request.headers[name]

        body = request.body if request.method in ("POST", "PUT", "PATCH") else None
        req = urllib.request.Request(target_url, data=body, headers=headers, method=request.method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
                content_type = resp.headers.get("Content-Type", "text/html")
                return HttpResponse(content, status=resp.status, content_type=content_type)
        except urllib.error.HTTPError as e:
            return HttpResponse(e.read(), status=e.code)
        except Exception as e:
            return HttpResponse(
                f"<h1>Mailpit non raggiungibile</h1><pre>{e}</pre>"
                "<p>Avvia Mailpit con il profilo <code>mailpit</code>:<br>"
                "<code>COMPOSE_PROFILES=mailpit</code> in <code>.env</code>, poi "
                "<code>docker compose up -d</code></p>",
                status=503,
                content_type="text/html",
            )
