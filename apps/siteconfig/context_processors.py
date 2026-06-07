from django.conf import settings

from apps.siteconfig.models import Impostazioni


def impostazioni(request):
    imp = Impostazioni.get()

    footer_rendered = imp.footer_testo
    if imp.footer_testo:
        try:
            from django.template import Context, Template
            ctx = {
                "titolo": imp.titolo,
                "sottotitolo": imp.sottotitolo,
                "versione": getattr(settings, "APP_VERSION", ""),
                "commit": getattr(settings, "APP_COMMIT", ""),
            }
            footer_rendered = Template(imp.footer_testo).render(Context(ctx))
        except Exception:
            footer_rendered = imp.footer_testo

    return {
        "impostazioni": imp,
        "footer_rendered": footer_rendered,
        "app_version": getattr(settings, "APP_VERSION", ""),
        "app_commit": getattr(settings, "APP_COMMIT", ""),
    }
