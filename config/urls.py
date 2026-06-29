# config/urls.py
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import PlanciaAuthenticateView, PlanciaPasswordChangeView
from apps.api.api import api
from apps.editions.views import HomeView
from apps.notifications.webhooks import AnymailWebhookDispatchView
from apps.siteconfig.views import FlowerProxyView, MailpitProxyView, PaginaStaticaPublicView
from config.error_views import page_not_found, server_error

handler404 = page_not_found
handler500 = server_error

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    # Override prima di allauth.urls: mfa_authenticate evita begin_authentication() inutile
    # (fix CSRF iOS Safari); password/change/ redirect al profilo invece della home.
    path("accounts/2fa/authenticate/", PlanciaAuthenticateView.as_view(), name="mfa_authenticate"),
    path("accounts/password/change/", PlanciaPasswordChangeView.as_view(), name="account_change_password"),
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path("utenti/", include("apps.accounts.urls", namespace="accounts")),
    path("", include("pwa.urls")),
    path("hijack/", include("hijack.urls")),
    path("edizioni/", include("apps.editions.urls", namespace="editions")),
    path("diari/", include("apps.diaries.urls", namespace="diaries")),
    path("valutazioni/", include("apps.evaluations.urls", namespace="evaluations")),
    path("notifiche/", include("apps.notifications.urls", namespace="notifications")),
    path("helpdesk/", include("apps.helpdesk.urls", namespace="helpdesk")),
    path("impostazioni/", include("apps.siteconfig.urls", namespace="siteconfig")),
    path("import/", include("apps.imports.urls", namespace="imports")),
    path("stats/", include("apps.stats.urls", namespace="stats")),
    path("api/v1/", api.urls),
    path("api/soci/", include("apps.org.urls")),
    path("api/diari/", include("apps.diaries.api_urls")),
    path("drive/", include("apps.storage_drive.urls", namespace="storage_drive")),
    path("anymail/webhook/", AnymailWebhookDispatchView.as_view(), name="anymail_webhook"),
    path("privacy/", PaginaStaticaPublicView.as_view(), {"slug": "privacy"}, name="pagina_privacy"),
    path("termini/", PaginaStaticaPublicView.as_view(), {"slug": "termini"}, name="pagina_termini"),
    path("mailadmin/", MailpitProxyView.as_view(), name="mailpit_proxy"),
    path("mailadmin/<path:path>", MailpitProxyView.as_view(), name="mailpit_proxy_path"),
    path("celery/", FlowerProxyView.as_view(), name="flower_proxy"),
    path("celery/<path:path>", FlowerProxyView.as_view(), name="flower_proxy_path"),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
