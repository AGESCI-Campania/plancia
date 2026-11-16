from django.conf import settings

from apps.siteconfig.models import Impostazioni
from apps.siteconfig.sito import footer_renderizzato


def impostazioni(request):
    imp = Impostazioni.get()
    return {
        "impostazioni": imp,
        "footer_rendered": footer_renderizzato(imp),
        "app_version": getattr(settings, "APP_VERSION", ""),
        "app_commit": getattr(settings, "APP_COMMIT", ""),
    }
