# config/urls.py
"""URL serviti da Django (Plancia 3: l'interfaccia è la SPA in `frontend/`, servita da nginx).

Restano qui: API (`/api/v1/`), allauth headless (`/_allauth/`), callback dei provider
social/SSO (`/accounts/<provider>/login/callback/`, con `HEADLESS_ONLY` allauth monta solo
quelle), admin, healthcheck, callback OAuth di Drive e Gmail SMTP, webhook Anymail e i
proxy Mailpit/Flower (solo Admin).
"""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from apps.api.api import api
from apps.notifications.webhooks import AnymailWebhookDispatchView
from apps.siteconfig.views import FlowerProxyView, GmailSMTPOAuthCallbackView, MailpitProxyView
from config.error_views import page_not_found, permission_denied, server_error
from config.health import healthz

handler403 = permission_denied
handler404 = page_not_found
handler500 = server_error


def _login_admin_dalla_spa(request, extra_context=None):
    """L'admin non ha un proprio form di accesso: si entra dalla SPA (password + MFA via
    allauth) e si torna all'admin con `next`."""
    destinazione = request.GET.get("next") or "/admin/"
    if not destinazione.startswith("/admin/"):  # niente redirect verso altri siti
        destinazione = "/admin/"
    return redirect(f"{settings.LOGIN_URL}?{urlencode({'next': destinazione})}")


admin.site.login = _login_admin_dalla_spa  # type: ignore[method-assign]

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    # Solo le callback dei provider social/SSO (HEADLESS_ONLY): la callback di Sestante è
    # /accounts/oidc/sestante/login/callback/, registrata nel blueprint del repo sestante.
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path("api/v1/", api.urls),
    path("drive/", include("apps.storage_drive.urls", namespace="storage_drive")),
    path(
        "impostazioni/gmail-smtp/oauth/callback/",
        GmailSMTPOAuthCallbackView.as_view(),
        name="gmail_smtp_oauth_callback",
    ),
    path("anymail/webhook/", AnymailWebhookDispatchView.as_view(), name="anymail_webhook"),
    path("mailadmin/", MailpitProxyView.as_view(), name="mailpit_proxy"),
    path("mailadmin/<path:path>", MailpitProxyView.as_view(), name="mailpit_proxy_path"),
    path("celery/", FlowerProxyView.as_view(), name="flower_proxy"),
    path("celery/<path:path>", FlowerProxyView.as_view(), name="flower_proxy_path"),
]

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls)), *urlpatterns]
    except ImportError:
        pass
