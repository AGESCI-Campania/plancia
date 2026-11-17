"""Dati pubblici del sito (titolo, footer, pagine, provider di login, versione).

Usati da `GET /api/v1/sito` (SPA).
"""
from __future__ import annotations

from typing import Any

from django.conf import settings

MANUALE_URL = "https://plancia.readthedocs.io/it/latest/"


def footer_renderizzato(imp) -> str:
    """`Impostazioni.footer_testo` reso come template Django con titolo/sottotitolo/versione/commit.

    In caso di errore di sintassi restituisce il testo così com'è.
    """
    if not imp.footer_testo:
        return ""
    from django.template import Context, Template

    from apps.siteconfig.versione import versione_installata

    try:
        ctx = {
            "titolo": imp.titolo,
            "sottotitolo": imp.sottotitolo,
            "versione": versione_installata(),
            "commit": getattr(settings, "APP_COMMIT", ""),
        }
        return Template(imp.footer_testo).render(Context(ctx))
    except Exception:
        return imp.footer_testo


def provider_login(request) -> list[dict[str, str]]:
    """Provider social/SSO configurati (quelli con client id), come nella pagina di login.

    `id` è quello da passare a `POST /_allauth/browser/v1/auth/provider/redirect`
    (`provider`), es. `google`, `microsoft`, `apple`, `sestante`.
    """
    from allauth.socialaccount.adapter import get_adapter

    try:
        providers = get_adapter().list_providers(request)
    except Exception:
        return []
    return [{"id": p.id, "nome": p.name} for p in providers]


def pagine_statiche() -> list[dict[str, str]]:
    from apps.siteconfig.models import PaginaStatica, SlugPagina

    titoli = dict(PaginaStatica.objects.values_list("slug", "titolo"))
    return [{"slug": slug, "titolo": titoli.get(slug) or label} for slug, label in SlugPagina.choices]


def pagina_statica(slug: str) -> dict[str, Any]:
    """Contenuto della pagina (privacy/termini); se mai salvata, un segnaposto. 404 se slug ignoto."""
    from django.core.exceptions import ObjectDoesNotExist

    from apps.siteconfig.models import PaginaStatica, SlugPagina

    if slug not in SlugPagina.values:
        raise ObjectDoesNotExist(slug)
    pagina = PaginaStatica.objects.filter(slug=slug).first()
    if pagina is None:
        return {
            "slug": slug, "titolo": SlugPagina(slug).label,
            "contenuto": "<p>Contenuto non ancora disponibile.</p>", "aggiornato_at": None,
        }
    return {
        "slug": pagina.slug, "titolo": pagina.titolo,
        "contenuto": pagina.contenuto, "aggiornato_at": pagina.aggiornato_at,
    }
