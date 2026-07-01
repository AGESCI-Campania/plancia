# apps/api/routers/system.py
from ninja import Router, Schema

router = Router(tags=["system"])


class AppStatusSchema(Schema):
    upgrade_required: bool
    upgrade_available: bool
    versione_minima: str
    deprecata_sotto: str
    messaggio: str
    funzioni_limitate: list[str]


@router.get(
    "/app-status", response=AppStatusSchema, auth=None, summary="Stato compatibilità versione app"
)
def app_status(request):
    """Restituisce informazioni sulla compatibilità della versione app corrente.

    Non richiede autenticazione. L'app chiama questo endpoint al lancio per mostrare
    messaggi di aggiornamento o disabilitare funzioni non supportate.
    """
    from apps.siteconfig.middleware import _versione_tuple
    from apps.siteconfig.models import Impostazioni

    imp = Impostazioni.get()
    app_version_str = getattr(request, "app_version", "") or request.META.get(
        "HTTP_X_APP_VERSION", ""
    )

    upgrade_required = False
    upgrade_available = False

    if app_version_str:
        if imp.app_versione_minima:
            upgrade_required = _versione_tuple(app_version_str) < _versione_tuple(
                imp.app_versione_minima
            )
        if imp.app_versione_deprecata and not upgrade_required:
            upgrade_available = _versione_tuple(app_version_str) < _versione_tuple(
                imp.app_versione_deprecata
            )

    return AppStatusSchema(
        upgrade_required=upgrade_required,
        upgrade_available=upgrade_available,
        versione_minima=imp.app_versione_minima,
        deprecata_sotto=imp.app_versione_deprecata,
        messaggio=imp.app_messaggio_aggiornamento,
        funzioni_limitate=imp.app_funzioni_limitate if upgrade_available else [],
    )
