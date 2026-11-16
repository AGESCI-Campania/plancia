import json
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.accounts.mixins import StaffPlanciaRequiredMixin
from apps.storage_drive.models import DriveCredenziali
from apps.storage_drive.oauth import (
    OAuthDriveErrore,
    avvia_oauth_drive,
    completa_oauth_drive,
    edizione_in_sessione,
)


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


class DriveOAuthInitView(StaffPlanciaRequiredMixin, View):
    """Avvia il flusso OAuth Google Drive e redirige a Google."""

    def get(self, request):
        return redirect(avvia_oauth_drive(request, request.GET.get("edizione", "")))


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


class DriveFolderListView(StaffPlanciaRequiredMixin, View):
    """AJAX – lista cartelle Drive per l'account collegato."""

    def get(self, request):
        account_email = request.GET.get("account", "")
        q = request.GET.get("q", "").strip()

        try:
            cred = DriveCredenziali.objects.get(account_email=account_email)
        except DriveCredenziali.DoesNotExist:
            return JsonResponse({"error": "Account non trovato"}, status=404)

        from apps.storage_drive.service import elenca_cartelle

        try:
            return JsonResponse({"cartelle": elenca_cartelle(cred, q)})
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)


class DriveCartellaCreaView(StaffPlanciaRequiredMixin, View):
    """AJAX – crea una cartella Drive e restituisce {id, nome}."""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON non valido"}, status=400)

        account_email = data.get("account", "")
        nome = data.get("nome", "").strip()
        parent_id = data.get("parent_id") or None

        if not nome:
            return JsonResponse({"error": "Nome obbligatorio"}, status=400)

        try:
            cred = DriveCredenziali.objects.get(account_email=account_email)
        except DriveCredenziali.DoesNotExist:
            return JsonResponse({"error": "Account non trovato"}, status=404)

        from apps.storage_drive.service import crea_cartella

        try:
            folder_id = crea_cartella(cred, nome, parent_id)
            return JsonResponse({"id": folder_id, "nome": nome})
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)


class DriveFolderInfoView(StaffPlanciaRequiredMixin, View):
    """AJAX – restituisce nome e webViewLink di una singola cartella Drive."""

    def get(self, request):
        account_email = request.GET.get("account", "")
        folder_id = request.GET.get("id", "").strip()

        if not folder_id:
            return JsonResponse({"error": "ID mancante"}, status=400)

        try:
            cred = DriveCredenziali.objects.get(account_email=account_email)
        except DriveCredenziali.DoesNotExist:
            return JsonResponse({"error": "Account non trovato"}, status=404)

        from apps.storage_drive.service import info_cartella

        try:
            return JsonResponse(info_cartella(cred, folder_id))
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)


class DriveEdizioneFolderUpdateView(StaffPlanciaRequiredMixin, View):
    """Aggiorna cartelle Drive e formato nome per un'edizione.

    Una volta che tutte e tre le impostazioni (cartella allegati, cartella output,
    formato nome) sono salvate, la configurazione si blocca e non può più essere
    modificata (regola in `service.configura_cartelle_edizione`).
    """

    def post(self, request, pk):
        from apps.editions.models import Edizione
        from apps.evaluations.actions import StatoNonValido
        from apps.storage_drive.service import configura_cartelle_edizione

        edizione = get_object_or_404(Edizione, pk=pk)
        try:
            bloccata = configura_cartelle_edizione(
                edizione,
                request.POST.get("drive_folder_allegati_id", ""),
                request.POST.get("drive_folder_output_id", ""),
                request.POST.get("cartella_diario_format", ""),
            )
        except StatoNonValido as exc:
            messages.error(request, str(exc))
            return redirect("editions:update", pk=pk)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("editions:update", pk=pk)

        if bloccata:
            messages.success(
                request,
                "Configurazione cartelle Drive salvata e bloccata. "
                "Le sottocartelle per i diari saranno create automaticamente.",
            )
        else:
            messages.success(request, "Cartelle Drive aggiornate.")
        return redirect("editions:update", pk=pk)
