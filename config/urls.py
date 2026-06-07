# config/urls.py
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.editions.views import HomeView
from apps.notifications.webhooks import AnymailWebhookDispatchView
from apps.siteconfig.views import FlowerProxyView, MailpitProxyView, PaginaStaticaPublicView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
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
    path("api/soci/", include("apps.org.urls")),
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
