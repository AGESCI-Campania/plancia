# apps/storage_drive/views.py
"""Callback OAuth Google Drive (l'avvio del flusso è `POST /api/v1/drive/oauth`)."""
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.views import View

from apps.storage_drive.oauth import OAuthDriveErrore, completa_oauth_drive, edizione_in_sessione


def url_spa_esito_oauth(edizione_pk: str, ok: bool, messaggio: str = "") -> str:
    """Pagina della SPA a cui torna la callback OAuth Drive.

    Con un'edizione: `/edizioni/<pk>?drive=ok|errore[&messaggio=…]`;
    senza: `/impostazioni/drive?esito=ok|errore[&messaggio=…]`.
    """
    if edizione_pk:
        params = {"drive": "ok" if ok else "errore"}
        base = f"/edizioni/{edizione_pk}"
    else:
        params = {"esito": "ok" if ok else "errore"}
        base = "/impostazioni/drive"
    if messaggio:
        params["messaggio"] = messaggio
    return f"{base}?{urlencode(params)}"


class DriveOAuthCallbackView(View):
    """Callback OAuth (percorso registrato presso Google): salva le credenziali e torna alla SPA."""

    def get(self, request):
        edizione_pk = edizione_in_sessione(request)
        try:
            esito = completa_oauth_drive(request)
        except OAuthDriveErrore as exc:
            return redirect(url_spa_esito_oauth(edizione_pk, False, str(exc)))
        return redirect(url_spa_esito_oauth(
            esito.edizione_pk, True, f"Account Drive {esito.email} collegato."
        ))
