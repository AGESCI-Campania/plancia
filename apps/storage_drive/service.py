# apps/storage_drive/service.py
"""Client Google Drive via OAuth. Vedi docs sez. 10.

Dipendenze opzionali: google-auth, google-api-python-client.
Se non installate il servizio lancia ImportError con messaggio esplicativo.
"""
from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.storage_drive.models import DriveCredenziali


def _build_drive_service(credenziali: DriveCredenziali):
    """Costruisce il client Drive autenticato, rinfrescando il token se necessario."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            "google-auth e google-api-python-client sono necessari per Drive. "
            "Esegui: uv add google-auth google-api-python-client"
        ) from exc

    creds = Credentials(
        token=credenziali.access_token,
        refresh_token=credenziali.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_client_id(),
        client_secret=_client_secret(),
    )

    if credenziali.scaduto:
        creds.refresh(Request())
        credenziali.access_token = creds.token
        expiry = creds.expiry
        if expiry is not None:
            from django.utils import timezone as tz
            if tz.is_naive(expiry):
                expiry = tz.make_aware(expiry)
        credenziali.expires_at = expiry
        credenziali.save(update_fields=["access_token", "expires_at", "aggiornato_at"])

    return build("drive", "v3", credentials=creds)


def _client_id() -> str:
    from django.conf import settings
    return getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")


def _client_secret() -> str:
    from django.conf import settings
    return getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")


def carica_file(
    credenziali: DriveCredenziali,
    nome_file: str,
    contenuto: bytes,
    mime_type: str,
    folder_id: str | None = None,
) -> dict:
    """Carica un file su Drive e restituisce i metadati (id, webViewLink, …)."""
    from googleapiclient.http import MediaIoBaseUpload

    service = _build_drive_service(credenziali)

    metadata: dict = {"name": nome_file}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(io.BytesIO(contenuto), mimetype=mime_type, resumable=False)
    file_meta = (
        service.files()
        .create(body=metadata, media_body=media, fields="id,name,size,webViewLink,mimeType")
        .execute()
    )
    return file_meta


def crea_cartella(
    credenziali: DriveCredenziali,
    nome: str,
    parent_id: str | None = None,
) -> str:
    """Crea una cartella su Drive e restituisce il suo id."""
    service = _build_drive_service(credenziali)
    metadata: dict = {
        "name": nome,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def carica_allegato_drive(allegato) -> None:
    """Carica un Allegato su Drive nella sottocartella del diario e aggiorna stato_sync.

    La sottocartella viene creata automaticamente se non esiste ancora.
    """
    from apps.diaries.models import StatoSync

    diario = allegato.diario
    edizione = diario.edizione

    if not edizione.drive_oauth_account:
        return

    assicura_cartelle_diario(diario)

    # Leggi l'istanza aggiornata per avere il folder_id appena creato
    diario.refresh_from_db(fields=["drive_folder_allegati_id"])
    folder_id = diario.drive_folder_allegati_id or edizione.drive_folder_allegati_id or None

    credenziali = _get_credenziali(edizione)

    if not allegato.file:
        return

    contenuto = allegato.file.read()
    mime = allegato.mime or "application/octet-stream"
    meta = carica_file(credenziali, allegato.nome, contenuto, mime, folder_id)

    allegato.drive_file_id = meta["id"]
    allegato.stato_sync = StatoSync.CARICATO
    allegato.file.delete(save=False)
    allegato.file = None
    allegato.save(update_fields=["drive_file_id", "stato_sync", "file"])


def carica_pdf_diario(diario) -> None:
    """Genera il PDF del diario, lo carica su Drive e crea il DriveFile."""
    from apps.exports.service import genera_pdf_diario
    from apps.storage_drive.models import DriveFile, TipoFile

    assicura_cartelle_diario(diario)

    pdf_bytes = genera_pdf_diario(diario)
    edizione = diario.edizione
    credenziali = _get_credenziali(edizione)
    # Usa la sottocartella del diario se disponibile, altrimenti la cartella dell'edizione
    folder_id = diario.drive_folder_output_id or edizione.drive_folder_output_id or None

    nome = f"Diario_{diario.squadriglia}_{edizione.anno}.pdf"
    meta = carica_file(credenziali, nome, pdf_bytes, "application/pdf", folder_id)

    DriveFile.objects.update_or_create(
        diario=diario,
        tipo=TipoFile.PDF,
        defaults={
            "drive_file_id": meta["id"],
            "nome": meta.get("name", nome),
            "mime": meta.get("mimeType", "application/pdf"),
            "dimensione": len(pdf_bytes),
            "edizione": edizione,
            "url_esterno": meta.get("webViewLink", ""),
        },
    )


def carica_excel_edizione(edizione) -> None:
    """Genera l'Excel degli esiti, lo carica su Drive e crea il DriveFile."""
    from apps.exports.service import genera_excel_edizione
    from apps.storage_drive.models import DriveFile, TipoFile

    excel_bytes = genera_excel_edizione(edizione)
    credenziali = _get_credenziali(edizione)
    folder_id = edizione.drive_folder_output_id or None

    nome = f"Esiti_GV_{edizione.anno}.xlsx"
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    meta = carica_file(credenziali, nome, excel_bytes, mime, folder_id)

    DriveFile.objects.update_or_create(
        edizione=edizione,
        tipo=TipoFile.EXCEL,
        defaults={
            "drive_file_id": meta["id"],
            "nome": meta.get("name", nome),
            "mime": meta.get("mimeType", mime),
            "dimensione": len(excel_bytes),
            "url_esterno": meta.get("webViewLink", ""),
        },
    )


def assicura_cartelle_diario(diario) -> None:
    """Crea su Drive (se mancanti) le sottocartelle per questo diario e salva gli ID.

    Va chiamata prima di caricare allegati o esportare il PDF del diario.
    Non fa nulla se le cartelle principali dell'edizione non sono configurate.
    """
    from apps.diaries.service import calcola_nome_cartella_diario

    edizione = diario.edizione
    if not edizione.drive_folder_allegati_id and not edizione.drive_folder_output_id:
        return

    credenziali = _get_credenziali(edizione)
    nome_cartella = calcola_nome_cartella_diario(diario)
    update_fields: list[str] = []

    if edizione.drive_folder_allegati_id and not diario.drive_folder_allegati_id:
        folder_id = crea_cartella(credenziali, nome_cartella, edizione.drive_folder_allegati_id)
        diario.drive_folder_allegati_id = folder_id
        update_fields.append("drive_folder_allegati_id")

    if edizione.drive_folder_output_id and not diario.drive_folder_output_id:
        folder_id = crea_cartella(credenziali, nome_cartella, edizione.drive_folder_output_id)
        diario.drive_folder_output_id = folder_id
        update_fields.append("drive_folder_output_id")

    if update_fields:
        diario.save(update_fields=update_fields)


def _get_credenziali(edizione) -> DriveCredenziali:
    from apps.storage_drive.models import DriveCredenziali

    account = edizione.drive_oauth_account
    if not account:
        raise ValueError(f"Nessun account Drive configurato per l'edizione {edizione}.")
    return DriveCredenziali.objects.get(account_email=account)
