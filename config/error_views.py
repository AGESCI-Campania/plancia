# config/error_views.py
"""Viste per le pagine di errore HTTP (404, 500, CSRF)."""
import logging

from django.core.mail import mail_admins
from django.shortcuts import render

logger = logging.getLogger(__name__)


def page_not_found(request, exception):
    """404 — pagina non trovata. Mostra template brandizzato e notifica gli admin."""
    _notify_404(request)
    return render(request, "404.html", status=404)


def server_error(request):
    """500 — errore interno. Usa template standalone (senza extends base.html).

    Non estende base.html per resistere a errori del tema, del DB o dei
    context processor. La notifica email agli admin è gestita da AdminEmailHandler
    nel logger django.request (vedi LOGGING in settings/base.py).
    """
    return render(request, "500.html", status=500)


def csrf_failure(request, reason=""):
    """CSRF token mancante o non valido. Mostra template brandizzato con istruzioni."""
    return render(request, "403_csrf.html", {"reason": reason}, status=403)


def _notify_404(request):
    """Invia email agli ADMINS per ogni 404. fail_silently=True per non mascherare l'errore."""
    try:
        path = request.path
        user = getattr(request, "user", None)
        user_info = getattr(user, "email", "anonimo") if user and user.is_authenticated else "anonimo"
        mail_admins(
            subject=f"404 Not Found: {path}",
            message=(
                f"URL: {request.build_absolute_uri()}\n"
                f"Referrer: {request.META.get('HTTP_REFERER', '—')}\n"
                f"User-Agent: {request.META.get('HTTP_USER_AGENT', '—')}\n"
                f"Utente: {user_info}\n"
            ),
            fail_silently=True,
        )
    except Exception:
        logger.exception("Impossibile inviare email di notifica per 404")
