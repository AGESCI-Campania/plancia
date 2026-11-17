# config/error_views.py
"""Pagine di errore HTTP (403, 404, 500, CSRF) dei percorsi serviti da Django.

L'interfaccia è la SPA servita da nginx: qui restano admin, callback OAuth, proxy e API.
Le pagine HTML sono file statici autonomi (`templates/403.html`, …: CSS inline, nessun
`{% extends %}`, nessun accesso al DB), così funzionano anche se il resto è guasto.
Sui percorsi dell'API (`/api/`, `/_allauth/`) la risposta è JSON.
"""
import logging

from django.core.mail import mail_admins
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.loader import get_template

logger = logging.getLogger(__name__)

_PREFISSI_API = ("/api/", "/_allauth/")


def _e_api(request: HttpRequest) -> bool:
    return request.path_info.startswith(_PREFISSI_API)


def _pagina(nome: str, status: int) -> HttpResponse:
    # Nessun contesto né context processor: il template è HTML statico.
    return HttpResponse(get_template(nome).render(), status=status)


def permission_denied(request: HttpRequest, exception=None) -> HttpResponse:
    """403 — permessi negati."""
    if _e_api(request):
        return JsonResponse({"detail": "Permesso negato."}, status=403)
    return _pagina("403.html", 403)


def page_not_found(request: HttpRequest, exception=None) -> HttpResponse:
    """404 — pagina non trovata; notifica gli admin."""
    _notify_404(request)
    if _e_api(request):
        return JsonResponse({"detail": "Non trovato."}, status=404)
    return _pagina("404.html", 404)


def server_error(request: HttpRequest) -> HttpResponse:
    """500 — errore interno. L'email agli admin la manda AdminEmailHandler (LOGGING)."""
    if _e_api(request):
        return JsonResponse({"detail": "Errore interno del server."}, status=500)
    return _pagina("500.html", 500)


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """CSRF token mancante o non valido (`CSRF_FAILURE_VIEW`)."""
    logger.warning(
        "CSRF failure | reason=%r | path=%s | Origin=%r | Referer=%r | User-Agent=%r",
        reason,
        request.path,
        request.META.get("HTTP_ORIGIN"),
        request.META.get("HTTP_REFERER"),
        request.META.get("HTTP_USER_AGENT", "")[:120],
    )
    if _e_api(request):
        return JsonResponse({"detail": "Token CSRF mancante o non valido."}, status=403)
    return _pagina("403_csrf.html", 403)


def _notify_404(request: HttpRequest) -> None:
    """Invia email agli ADMINS per ogni 404; un errore di invio non deve mascherare il 404."""
    try:
        user = getattr(request, "user", None)
        user_info = getattr(user, "email", "anonimo") if user and user.is_authenticated else "anonimo"
        mail_admins(
            subject=f"404 Not Found: {request.path}",
            message=(
                f"URL: {request.build_absolute_uri()}\n"
                f"Referrer: {request.META.get('HTTP_REFERER', '—')}\n"
                f"User-Agent: {request.META.get('HTTP_USER_AGENT', '—')}\n"
                f"Utente: {user_info}\n"
            ),
        )
    except Exception:
        logger.exception("Impossibile inviare email di notifica per 404")
