# apps/storage_drive/views.py
import json

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.accounts.mixins import StaffPlanciaRequiredMixin
from apps.storage_drive.models import DriveCredenziali

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def _oauth_client_config() -> dict:
    return {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


class DriveOAuthInitView(StaffPlanciaRequiredMixin, View):
    """Avvia il flusso OAuth Google Drive e redirige a Google."""

    def get(self, request):
        import base64
        import hashlib
        import secrets

        from google_auth_oauthlib.flow import Flow

        edizione_pk = request.GET.get("edizione", "")

        # PKCE (richiesto da Google per tutti i client OAuth da ottobre 2024)
        code_verifier = secrets.token_urlsafe(96)
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .decode()
            .rstrip("=")
        )

        flow = Flow.from_client_config(
            _oauth_client_config(),
            scopes=DRIVE_SCOPES,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
        request.session["drive_oauth_state"] = state
        request.session["drive_oauth_edizione"] = edizione_pk
        request.session["drive_oauth_code_verifier"] = code_verifier
        return redirect(auth_url)


class DriveOAuthCallbackView(View):
    """Callback OAuth: scambia il codice, salva DriveCredenziali, torna all'edizione."""

    def get(self, request):
        import os

        from django.utils import timezone
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build

        state = request.session.pop("drive_oauth_state", None)
        edizione_pk = request.session.pop("drive_oauth_edizione", None)
        code_verifier = request.session.pop("drive_oauth_code_verifier", None)

        if not state or state != request.GET.get("state"):
            messages.error(request, "Sessione OAuth non valida. Riprova.")
            return redirect("editions:list")

        # In dev il redirect URI è http: oauthlib richiede https salvo questa env var
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

        flow = Flow.from_client_config(
            _oauth_client_config(),
            scopes=DRIVE_SCOPES,
            state=state,
            redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
        )
        flow.fetch_token(
            authorization_response=request.build_absolute_uri(),
            code_verifier=code_verifier,
        )
        creds = flow.credentials

        service = build("oauth2", "v2", credentials=creds)
        email = service.userinfo().get().execute().get("email", "")

        expires_at = None
        if creds.expiry:
            expires_at = (
                timezone.make_aware(creds.expiry)
                if creds.expiry.tzinfo is None
                else creds.expiry
            )

        DriveCredenziali.objects.update_or_create(
            account_email=email,
            defaults={
                "access_token": creds.token,
                "refresh_token": creds.refresh_token or "",
                "expires_at": expires_at,
            },
        )

        if edizione_pk:
            from apps.editions.models import Edizione
            try:
                ed = Edizione.objects.get(pk=edizione_pk)
                ed.drive_oauth_account = email
                ed.save(update_fields=["drive_oauth_account"])
                messages.success(request, f"Account Drive {email} collegato.")
                return redirect("editions:update", pk=edizione_pk)
            except Edizione.DoesNotExist:
                pass

        messages.success(request, f"Account Drive {email} collegato.")
        return redirect("editions:list")


class DriveFolderListView(StaffPlanciaRequiredMixin, View):
    """AJAX – lista cartelle Drive per l'account collegato."""

    def get(self, request):
        account_email = request.GET.get("account", "")
        q = request.GET.get("q", "").strip()

        try:
            cred = DriveCredenziali.objects.get(account_email=account_email)
        except DriveCredenziali.DoesNotExist:
            return JsonResponse({"error": "Account non trovato"}, status=404)

        from apps.storage_drive.service import _build_drive_service

        try:
            service = _build_drive_service(cred)
            query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
            if q:
                query += f" and name contains '{q.replace(chr(39), '')}'"
            results = (
                service.files()
                .list(q=query, pageSize=20, fields="files(id,name)", orderBy="name")
                .execute()
            )
            return JsonResponse({"cartelle": results.get("files", [])})
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

        from apps.storage_drive.service import _build_drive_service

        try:
            service = _build_drive_service(cred)
            meta = (
                service.files()
                .get(fileId=folder_id, fields="id,name,webViewLink")
                .execute()
            )
            return JsonResponse({"name": meta.get("name", ""), "url": meta.get("webViewLink", "")})
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)


class DriveEdizioneFolderUpdateView(StaffPlanciaRequiredMixin, View):
    """Aggiorna cartelle Drive e formato nome per un'edizione.

    Una volta che tutte e tre le impostazioni (cartella allegati, cartella output,
    formato nome) sono salvate, la configurazione si blocca e non può più essere
    modificata.
    """

    def post(self, request, pk):
        from apps.diaries.service import valida_formato_cartella
        from apps.editions.models import Edizione

        edizione = get_object_or_404(Edizione, pk=pk)

        if edizione.cartelle_configurate:
            messages.error(
                request,
                "Configurazione cartelle Drive bloccata: le cartelle e il formato "
                "non possono essere modificati dopo la prima configurazione.",
            )
            return redirect("editions:update", pk=pk)

        nuovo_allegati = request.POST.get("drive_folder_allegati_id", "").strip()
        nuovo_output = request.POST.get("drive_folder_output_id", "").strip()
        nuovo_formato = request.POST.get("cartella_diario_format", "").strip()

        errore = valida_formato_cartella(nuovo_formato) if nuovo_formato else None
        if errore:
            messages.error(request, f"Formato non valido: {errore}")
            return redirect("editions:update", pk=pk)

        edizione.drive_folder_allegati_id = nuovo_allegati
        edizione.drive_folder_output_id = nuovo_output
        if nuovo_formato:
            edizione.cartella_diario_format = nuovo_formato
        edizione.save(
            update_fields=[
                "drive_folder_allegati_id",
                "drive_folder_output_id",
                "cartella_diario_format",
            ]
        )

        if edizione.cartelle_configurate:
            messages.success(
                request,
                "Configurazione cartelle Drive salvata e bloccata. "
                "Le sottocartelle per i diari saranno create automaticamente.",
            )
        else:
            messages.success(request, "Cartelle Drive aggiornate.")
        return redirect("editions:update", pk=pk)
