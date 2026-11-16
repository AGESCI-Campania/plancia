"""Dati pubblici del sito: leggibili anche prima del login e durante la manutenzione."""
from __future__ import annotations

from django.conf import settings
from ninja import Router

from apps.api.errors import ErroreSchema
from apps.api.schemas.sito import PaginaSchema, SitoSchema

router = Router(tags=["sito"])


@router.get("", response=SitoSchema, auth=None, summary="Titolo, footer, pagine, login, versione")
def sito(request):
    """Tutto ciò che serve alla SPA prima del login: testi, footer, pagine statiche,
    stato della manutenzione, provider di login configurati e versione del server."""
    from apps.siteconfig import sito as dati
    from apps.siteconfig.manutenzione import messaggio_manutenzione
    from apps.siteconfig.models import Impostazioni
    from apps.siteconfig.versione import versione_installata

    imp = Impostazioni.get()
    return {
        "titolo": imp.titolo,
        "sottotitolo": imp.sottotitolo,
        "versione": versione_installata(),
        "commit": getattr(settings, "APP_COMMIT", "") or "",
        "footer": {
            "testo": dati.footer_renderizzato(imp),
            "links": [
                {"tipo": link.tipo, "url": link.url,
                 "etichetta": link.etichetta or link.get_tipo_display()}
                for link in imp.footer_links.all()
            ],
            "manuale_url": dati.MANUALE_URL,
        },
        "pagine": dati.pagine_statiche(),
        "manutenzione": {
            "attiva": imp.manutenzione,
            "messaggio": messaggio_manutenzione(imp) if imp.manutenzione else "",
        },
        "login": {"locale": True, "provider": dati.provider_login(request)},
    }


@router.get("/pagine/{slug}", response={200: PaginaSchema, 404: ErroreSchema}, auth=None,
            summary="Contenuto di una pagina statica (privacy, termini)")
def pagina(request, slug: str):
    from apps.siteconfig.sito import pagina_statica

    return pagina_statica(slug)
