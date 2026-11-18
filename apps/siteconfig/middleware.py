# apps/siteconfig/middleware.py
import json
import time

from django.conf import settings as django_settings
from django.core.cache import cache
from django.http import HttpResponse
from django.template.loader import render_to_string

_API_PREFIXES = ("/api/v1/", "/_allauth/")
_API_V1 = "/api/v1/"
_BYPASS_MANUTENZIONE_API = ("/api/v1/sito", "/api/v1/aggiornamenti")


def _versione_tuple(v: str) -> tuple[int, ...]:
    try:
        from packaging.version import Version

        parsed = Version(v)
        return (parsed.major, parsed.minor, parsed.micro)
    except Exception:
        pass
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def _rate_limit_check(key: str, max_count: int, window_seconds: int) -> tuple[bool, int]:
    """Controlla il rate limit con fixed-window Redis. Restituisce (consentito, retry_after)."""
    if max_count == 0:
        return True, 0
    bucket = int(time.time() / window_seconds)
    cache_key = f"rl:{key}:{window_seconds}:{bucket}"
    try:
        count = cache.incr(cache_key)
    except ValueError:
        added = cache.add(cache_key, 1, window_seconds * 2)
        count = 1 if added else cache.incr(cache_key)
    if count > max_count:
        remaining = window_seconds - (int(time.time()) % window_seconds) + 1
        return False, remaining
    return True, 0


def _chiave_client(request) -> str:
    """Chi conta per il rate limit: la sessione (app o SPA) se esiste davvero, altrimenti l'IP.

    Per sessione e non per IP: più utenti dietro lo stesso NAT (una sede, un campo) non si
    bloccano a vicenda. Un cookie inventato non vale (la sessione deve esistere), quindi non
    serve a scavalcare il limite. L'IP è quello vero del client dietro Caddy + nginx, come
    per axes (il primo X-Forwarded-For lo sceglie il client).
    """
    import hashlib
    from importlib import import_module

    from apps.siteconfig.axes_helpers import ip_client_dietro_proxy

    token = request.META.get("HTTP_X_SESSION_TOKEN", "")
    if token:
        return "tok:" + hashlib.sha256(token.encode()).hexdigest()[:32]
    chiave_sessione = request.COOKIES.get(django_settings.SESSION_COOKIE_NAME, "")
    if chiave_sessione:
        store = import_module(django_settings.SESSION_ENGINE).SessionStore
        if store().exists(chiave_sessione):
            return "ses:" + hashlib.sha256(chiave_sessione.encode()).hexdigest()[:32]
    return f"ip:{ip_client_dietro_proxy(request) or 'sconosciuto'}"


class ApiRateLimitMiddleware:
    """Rate limiting per /api/v1/ basato su Redis (fixed window).

    Identifica il client per sessione (X-Session-Token o cookie, se la sessione esiste) o per
    IP (vedi `_chiave_client`).
    Limiti configurabili in Impostazioni (per minuto e per ora).
    Restituisce 429 JSON con header Retry-After se il limite è superato.
    Deve stare dopo CorsMiddleware e prima di SessionMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith(_API_V1):
            from apps.siteconfig.models import Impostazioni

            imp = Impostazioni.get()
            if imp.api_ratelimit_abilitato:
                client_key = _chiave_client(request)

                if imp.api_ratelimit_per_minuto:
                    ok, retry_after = _rate_limit_check(
                        client_key, imp.api_ratelimit_per_minuto, 60
                    )
                    if not ok:
                        return _too_many_requests(retry_after)

                if imp.api_ratelimit_per_ora:
                    ok, retry_after = _rate_limit_check(client_key, imp.api_ratelimit_per_ora, 3600)
                    if not ok:
                        return _too_many_requests(retry_after)

        return self.get_response(request)


class AppVersionMiddleware:
    """Controlla X-App-Version per le chiamate /api/v1/.

    - Versione < app_versione_minima → 426 Upgrade Required (blocco hard).
    - Versione < app_versione_deprecata → prosegue con header X-App-Upgrade-Warning: true.
    - Header assente → nessuna azione (browser web).

    Inietta request.app_version (str) e request.app_update_available (bool)
    per uso nei router.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.app_version = ""
        request.app_update_available = False

        if request.path_info.startswith(_API_V1):
            app_version_str = request.META.get("HTTP_X_APP_VERSION", "")
            if app_version_str:
                request.app_version = app_version_str
                from apps.siteconfig.models import Impostazioni

                imp = Impostazioni.get()

                if imp.app_versione_minima and _versione_tuple(app_version_str) < _versione_tuple(
                    imp.app_versione_minima
                ):
                    return _upgrade_required(imp)

                if imp.app_versione_deprecata and _versione_tuple(
                    app_version_str
                ) < _versione_tuple(imp.app_versione_deprecata):
                    request.app_update_available = True

        response = self.get_response(request)

        if getattr(request, "app_update_available", False):
            response["X-App-Upgrade-Warning"] = "true"

        return response


def _too_many_requests(retry_after: int) -> HttpResponse:
    return HttpResponse(
        json.dumps(
            {
                "detail": f"Troppe richieste. Riprova tra {retry_after} secondi.",
                "retry_after": retry_after,
            }
        ),
        content_type="application/json",
        status=429,
        headers={"Retry-After": str(retry_after)},
    )


def _upgrade_required(imp) -> HttpResponse:
    return HttpResponse(
        json.dumps(
            {
                "detail": imp.app_messaggio_aggiornamento
                or "Versione app non supportata. Aggiorna l'app per continuare.",
                "upgrade_required": True,
                "versione_minima": imp.app_versione_minima,
            }
        ),
        content_type="application/json",
        status=426,
    )


class AxesSettingsSyncMiddleware:
    """Sincronizza AXES_USE_ATTEMPT_EXPIRATION da Impostazioni prima che AxesMiddleware processi la request.

    Deve stare in MIDDLEWARE subito PRIMA di axes.middleware.AxesMiddleware.
    Gunicorn usa worker sync mono-thread: update di settings per processo è thread-safe.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.siteconfig.models import Impostazioni

        imp = Impostazioni.get()
        django_settings.AXES_USE_ATTEMPT_EXPIRATION = imp.axes_use_attempt_expiration
        return self.get_response(request)


class MaintenanceModeMiddleware:
    """Se Impostazioni.manutenzione e' attiva, mostra una pagina di cortesia
    a tutti TRANNE gli amministratori (ruolo attivo Admin o superuser). Vedi docs sez. 15.

    Il login headless (`/_allauth/`) resta aperto, altrimenti un Admin non potrebbe entrare
    dalla SPA: chi non è Admin, una volta entrato, riceve comunque 503 su `/api/v1/`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.accounts.models import Ruolo
        from apps.siteconfig.models import Impostazioni

        imp = Impostazioni.get()
        user = getattr(request, "user", None)
        is_admin = bool(
            user and user.is_authenticated and (user.is_superuser or user.ruolo == Ruolo.ADMIN)
        )
        path = request.path_info
        is_api = any(path.startswith(p) for p in _API_PREFIXES)
        # admin, login e healthcheck bypassano in silenzio; API ricevono 503 JSON invece di HTML
        # /api/v1/sito (pubblico: dice alla SPA che c'è manutenzione e con quale messaggio) e
        # /api/v1/aggiornamenti/ (solo Admin, controllato dal router: la pagina di aggiornamento
        # fa polling dello stato mentre aggiorna.sh tiene attiva la manutenzione) restano raggiungibili.
        bypass = (
            is_admin
            or path.startswith("/_allauth/")
            or path.startswith("/admin")
            or path.startswith("/accounts")
            or path == "/healthz/"
            or any(path.startswith(p) for p in _BYPASS_MANUTENZIONE_API)
        )
        if imp.manutenzione and not bypass:
            from apps.siteconfig.manutenzione import messaggio_manutenzione

            messaggio = messaggio_manutenzione(imp)
            if is_api:
                return HttpResponse(
                    json.dumps({"detail": messaggio, "maintenance": True}),
                    content_type="application/json",
                    status=503,
                )
            # Percorsi Django rimasti (admin escluso, callback, proxy): pagina statica autonoma.
            # La SPA è servita da nginx e legge la manutenzione da /api/v1/sito.
            html = render_to_string("siteconfig/manutenzione.html", {"messaggio": messaggio})
            return HttpResponse(html, status=503)
        return self.get_response(request)
