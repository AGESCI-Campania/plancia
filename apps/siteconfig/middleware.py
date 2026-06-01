# apps/siteconfig/middleware.py
from django.shortcuts import render


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
        # lascia passare admin, login e admin-site anche in manutenzione
        bypass = is_admin or path.startswith("/admin") or path.startswith("/accounts")
        if imp.manutenzione and not bypass:
            return render(request, "siteconfig/maintenance.html", status=503)
        return self.get_response(request)
