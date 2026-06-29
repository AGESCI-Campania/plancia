# apps/siteconfig/middleware.py
import json

from django.conf import settings as django_settings
from django.http import HttpResponse
from django.shortcuts import render

_API_PREFIXES = ("/api/v1/", "/_allauth/")


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
    a tutti TRANNE gli amministratori. Vedi docs sez. 15.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.siteconfig.models import Impostazioni

        imp = Impostazioni.get()
        user = getattr(request, "user", None)
        is_admin = bool(user and user.is_authenticated and user.is_superuser)
        path = request.path_info
        is_api = any(path.startswith(p) for p in _API_PREFIXES)
        # admin e login bypassano in silenzio; API ricevono 503 JSON invece di HTML
        bypass = is_admin or path.startswith("/admin") or path.startswith("/accounts")
        if imp.manutenzione and not bypass:
            if is_api:
                return HttpResponse(
                    json.dumps({"detail": "Servizio in manutenzione. Riprovare più tardi."}),
                    content_type="application/json",
                    status=503,
                )
            return render(request, "siteconfig/maintenance.html", status=503)
        return self.get_response(request)
