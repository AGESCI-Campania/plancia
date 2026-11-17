# apps/diaries/service.py
"""Logica di dominio per i Diari di Bordo."""
from __future__ import annotations

import contextlib
import re
import unicodedata

from apps.editions.models import CARTELLA_DIARIO_FORMAT_DEFAULT

VARIABILI_FORMATO = [
    "{id_univoco}",
    "{edizione}",
    "{nome_gruppo}",
    "{nome_zona}",
    "{nome_reparto}",
    "{nome_squadriglia}",
    "{specialita}",
]

_DUMMY_VALORI = {
    "id_univoco": "00001",
    "edizione": "2026",
    "nome_gruppo": "Gruppo",
    "nome_zona": "Zona",
    "nome_reparto": "Reparto",
    "nome_squadriglia": "Squadriglia",
    "specialita": "Campismo",
}


def valida_formato_cartella(fmt: str) -> str | None:
    """Restituisce il messaggio di errore oppure None se il formato è valido."""
    if not fmt:
        return "Il formato non può essere vuoto."
    if "{id_univoco}" not in fmt:
        return "Il formato deve contenere {id_univoco}."
    try:
        fmt.format(**_DUMMY_VALORI)
    except KeyError as exc:
        return f"Variabile non riconosciuta: {exc}. Usa solo le variabili previste."
    return None


def sanitizza_nome_cartella(s: str) -> str:
    """Rimuove caratteri non validi per nomi cartella Drive/filesystem."""
    # Decomponi e rimuovi diacritici
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Spazi e separatori → underscore
    s = re.sub(r"[\s/\\]+", "_", s)
    # Caratteri vietati su Drive/filesystem → rimossi
    s = re.sub(r'[<>:"|?*\x00-\x1f]', "", s)
    # Underscore ripetuti → uno solo
    s = re.sub(r"_+", "_", s)
    # Tronca a 100 caratteri e rimuovi underscore iniziali/finali
    s = s.strip("_")[:100].strip("_")
    return s or "diario"


def calcola_nome_cartella_diario(diario) -> str:
    """Restituisce il nome sanificato della sottocartella per questo diario."""
    edizione = diario.edizione
    squadriglia = diario.squadriglia
    reparto = squadriglia.reparto
    gruppo = reparto.gruppo
    zona = gruppo.zona

    specialita = ""
    with contextlib.suppress(Exception):
        specialita = diario.anagrafica.specialita or ""

    fmt = edizione.cartella_diario_format or CARTELLA_DIARIO_FORMAT_DEFAULT

    raw = fmt.format(
        id_univoco=f"{diario.pk:05d}",
        edizione=str(edizione.anno),
        nome_gruppo=gruppo.nome,
        nome_zona=zona.nome,
        nome_reparto=reparto.nome,
        nome_squadriglia=squadriglia.nome,
        specialita=specialita,
    )
    return sanitizza_nome_cartella(raw)


# ---------------------------------------------------------------------------
# Compilazione
# ---------------------------------------------------------------------------

def inizia_se_necessario(diario) -> None:
    """NON_INIZIATO → IN_COMPILAZIONE al primo salvataggio di un modulo o di una foto."""
    from apps.diaries.models import StatoDiario

    if diario.stato == StatoDiario.NON_INIZIATO:
        diario.inizia()


def rinomina_squadriglia(diario, nuovo_nome: str) -> bool:
    """Rinomina la squadriglia nel DB e le cartelle Drive del diario. True se il nome è cambiato.

    Drive non è critico: se fallisce, il rename a DB resta valido.
    """
    nuovo_nome = (nuovo_nome or "").strip()
    squadriglia = diario.squadriglia
    if not nuovo_nome or nuovo_nome == squadriglia.nome:
        return False
    squadriglia.nome = nuovo_nome
    squadriglia.save(update_fields=["nome"])

    if not diario.edizione.drive_oauth_account:
        return True
    try:
        from apps.storage_drive.service import _build_drive_service, _get_credenziali

        service = _build_drive_service(_get_credenziali(diario.edizione))
        nuovo_nome_cartella = calcola_nome_cartella_diario(diario)
        for folder_id in filter(None, [diario.drive_folder_allegati_id, diario.drive_folder_output_id]):
            with contextlib.suppress(Exception):
                service.files().update(
                    fileId=folder_id, body={"name": nuovo_nome_cartella}, fields="id",
                ).execute()
    except Exception:  # noqa: BLE001 - Drive non critico
        pass
    return True


def incrementa_versione(modulo) -> None:
    """Incrementa `version` di un modulo salvato fuori dall'API (form web), per i conflitti 409."""
    from django.db.models import F

    if modulo is not None and modulo.pk and hasattr(modulo, "version"):
        type(modulo).objects.filter(pk=modulo.pk).update(version=F("version") + 1)


# ---------------------------------------------------------------------------
# Cambio referenti (Capo Squadriglia / Capo Reparto)
# ---------------------------------------------------------------------------

def _socio_referente(socio_id, categoria: str, campo: str, etichetta: str):
    from django.core.exceptions import ValidationError

    from apps.org.models import Socio

    if socio_id in (None, ""):
        raise ValidationError({campo: [f"Seleziona un {etichetta}."]})
    try:
        return Socio.objects.get(pk=int(socio_id), categoria=categoria, provvisorio=False)
    except (Socio.DoesNotExist, ValueError, TypeError):
        raise ValidationError({campo: [f"{etichetta} non valido."]}) from None


def cambia_csq(diario, socio_id, user, campo: str = "socio_id"):
    """Sostituisce il Capo Squadriglia del diario. Restituisce (nuovo, vecchio).

    PermissionDenied se l'utente non può; ValidationError se il socio non è un ragazzo valido.
    """
    from django.core.exceptions import PermissionDenied

    from apps.diaries.permessi import puo_cambiare_csq

    if not puo_cambiare_csq(user, diario):
        raise PermissionDenied("Non puoi cambiare il Capo Squadriglia di questo diario.")
    nuovo = _socio_referente(socio_id, "ragazzo", campo, "Capo Squadriglia")
    vecchio = diario.csq
    diario.csq = nuovo
    diario.save(update_fields=["csq"])
    return nuovo, vecchio


def cambia_crp(diario, socio_id, user, campo: str = "socio_id"):
    """Sostituisce il Capo Reparto del diario (solo staff, prima dell'invio). (nuovo, vecchio)."""
    from django.core.exceptions import PermissionDenied

    from apps.diaries.permessi import puo_cambiare_crp

    if not puo_cambiare_crp(user, diario):
        raise PermissionDenied("Non puoi cambiare il Capo Reparto di questo diario.")
    nuovo = _socio_referente(socio_id, "capo", campo, "Capo Reparto")
    vecchio = diario.crp
    diario.crp = nuovo
    diario.save(update_fields=["crp"])
    return nuovo, vecchio


def diari_cambio_crp_reparto(reparto):
    """Diari del reparto non ancora inviati (quelli toccati dal cambio Capo Reparto in blocco)."""
    from apps.diaries.models import Diario
    from apps.diaries.permessi import STATI_PRIMA_INVIO

    return (
        Diario.objects.filter(squadriglia__reparto=reparto, stato__in=STATI_PRIMA_INVIO)
        .select_related("squadriglia", "csq", "crp", "edizione")
        .order_by("edizione__anno", "squadriglia__nome")
    )


def cambia_crp_reparto(reparto, socio_id, user, campo: str = "socio_id"):
    """Imposta il Capo Reparto su tutti i diari non inviati del reparto. (nuovo, numero diari)."""
    from django.core.exceptions import PermissionDenied

    from apps.diaries.permessi import puo_cambiare_crp_reparto

    if not puo_cambiare_crp_reparto(user):
        raise PermissionDenied("Operazione riservata alla gestione della piattaforma.")
    nuovo = _socio_referente(socio_id, "capo", campo, "Capo Reparto")
    n = diari_cambio_crp_reparto(reparto).update(crp=nuovo)
    return nuovo, n


# ---------------------------------------------------------------------------
# Allegati (foto)
# ---------------------------------------------------------------------------

MIME_ALLEGATI_CONSENTITI = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_BYTES_ALLEGATO = 20 * 1024 * 1024  # 20 MB


class FileNonDisponibile(Exception):
    """Il contenuto dell'allegato non è recuperabile (né in locale né su Drive)."""


def ridimensiona_immagine(file_obj, max_px: int) -> tuple[bytes, str, str]:
    """Ridimensiona l'immagine al lato maggiore `max_px` (JPEG q85). (bytes, mime, nome).

    Se Pillow non riesce ad aprire il file (es. HEIC senza plugin), restituisce l'originale.
    """
    import io
    import os

    from PIL import Image

    nome_orig = getattr(file_obj, "name", "foto.jpg") or "foto.jpg"
    try:
        file_obj.seek(0)
        img: Image.Image = Image.open(file_obj)
        img.load()
    except Exception:  # noqa: BLE001 - formato non leggibile: si tiene l'originale
        file_obj.seek(0)
        return file_obj.read(), getattr(file_obj, "content_type", "image/jpeg"), nome_orig

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_px:
        ratio = max_px / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    nome_base = os.path.splitext(nome_orig)[0]
    return buf.getvalue(), "image/jpeg", f"{nome_base}.jpg"


def carica_allegato(diario, user, modulo: str, file):
    """Valida, ridimensiona (`Impostazioni.allegati_max_px`) e salva una foto; accoda l'upload Drive.

    PermissionDenied se l'utente non può caricare; ValidationError per modulo/file non validi.
    """
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.core.files.base import ContentFile

    from apps.diaries.models import MODULI_FOTO, Allegato, StatoSync
    from apps.diaries.permessi import puo_caricare_allegati
    from apps.siteconfig.models import Impostazioni

    if not puo_caricare_allegati(user, diario):
        raise PermissionDenied("Non puoi caricare foto in questo diario.")
    if modulo not in MODULI_FOTO:
        raise ValidationError({"modulo": ["Modulo non valido."]})
    if not file:
        raise ValidationError({"file": ["Nessun file."]})
    if file.content_type not in MIME_ALLEGATI_CONSENTITI:
        raise ValidationError({"file": [f"Tipo non consentito: {file.content_type}"]})
    if file.size > MAX_BYTES_ALLEGATO:
        raise ValidationError({"file": ["File troppo grande (max 20 MB)."]})

    inizia_se_necessario(diario)
    max_px = Impostazioni.get().allegati_max_px or 1024
    img_bytes, img_mime, img_nome = ridimensiona_immagine(file, max_px)

    drive_configurato = bool(diario.edizione.drive_oauth_account)
    allegato = Allegato.objects.create(
        diario=diario,
        modulo=modulo,
        nome=img_nome,
        mime=img_mime,
        dimensione=len(img_bytes),
        file=ContentFile(img_bytes, name=img_nome),
        caricato_da=user,
        stato_sync=StatoSync.IN_CODA if drive_configurato else StatoSync.LOCALE,
    )
    if drive_configurato:
        from apps.storage_drive.tasks import task_carica_allegato_drive

        task_carica_allegato_drive.delay(allegato.pk)
    return allegato


def elimina_allegato(diario, allegato, user) -> None:
    """Elimina la foto (file locale compreso). PermissionDenied se non consentito."""
    from django.core.exceptions import PermissionDenied

    from apps.diaries.permessi import puo_eliminare_allegati

    if not puo_eliminare_allegati(user, diario):
        raise PermissionDenied("Non puoi eliminare foto di questo diario.")
    if allegato.file:
        allegato.file.delete(save=False)
    allegato.delete()


def scarica_da_drive(edizione, file_id: str) -> bytes:
    """Scarica un file da Drive con le credenziali OAuth dell'edizione."""
    import io

    from googleapiclient.http import MediaIoBaseDownload

    from apps.storage_drive.service import _build_drive_service, _get_credenziali

    service = _build_drive_service(_get_credenziali(edizione))
    req = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req, chunksize=4 * 1024 * 1024)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


def contenuto_allegato(diario, allegato) -> bytes:
    """Byte della foto: file locale se non ancora su Drive, altrimenti da Drive."""
    if not allegato.drive_file_id:
        if not allegato.file:
            raise FileNonDisponibile("File non disponibile.")
        with allegato.file.open("rb") as f:
            return f.read()
    try:
        return scarica_da_drive(diario.edizione, allegato.drive_file_id)
    except Exception as exc:  # noqa: BLE001
        raise FileNonDisponibile("File non disponibile su Drive.") from exc


def miniatura(contenuto: bytes, lato: int) -> bytes:
    """JPEG ridimensionato al lato maggiore `lato` (anteprime negli elenchi)."""
    import io

    buf = io.BytesIO(contenuto)
    buf.name = "miniatura.jpg"
    dati, _mime, _nome = ridimensiona_immagine(buf, lato)
    return dati


# ---------------------------------------------------------------------------
# PDF del diario (moduli 1–6, mai la valutazione)
# ---------------------------------------------------------------------------

PDF_LOCK_TTL = 1800  # 30 minuti


class StatoPdf:
    PRONTO = "pronto"                # in cache su Drive, oppure Drive non configurato (generato al volo)
    DA_GENERARE = "da_generare"      # Drive configurato, nessuna cache, nessuna generazione in corso
    IN_GENERAZIONE = "in_generazione"
    BLOCCATO = "bloccato"            # generazione massiva in corso per l'edizione


def pdf_lock_key(diario_pk: int) -> str:
    """Stessa chiave usata da `apps.exports.tasks.task_genera_pdf_diario`."""
    return f"pdf_task_lock:{diario_pk}"


def nome_pdf(diario) -> str:
    return f"Diario_{diario.squadriglia.nome}_{diario.edizione.anno}.pdf"


def pdf_in_cache(diario):
    """`DriveFile` del PDF su Drive, se esiste."""
    from apps.storage_drive.models import DriveFile, TipoFile

    return (
        DriveFile.objects.filter(diario=diario, tipo=TipoFile.PDF).exclude(drive_file_id="").first()
    )


def stato_pdf(diario) -> dict:
    """Stato del PDF: `{"stato", "messaggio", "sincrono"}` (sincrono = generato alla richiesta)."""
    from django.core.cache import cache

    from apps.exports.tasks import lock_key_massivo

    if not diario.edizione.drive_oauth_account:
        return {"stato": StatoPdf.PRONTO, "sincrono": True,
                "messaggio": "Il PDF viene generato al momento del download."}
    if pdf_in_cache(diario):
        return {"stato": StatoPdf.PRONTO, "sincrono": False, "messaggio": "Il PDF è pronto."}
    if cache.get(pdf_lock_key(diario.pk)):
        return {"stato": StatoPdf.IN_GENERAZIONE, "sincrono": False,
                "messaggio": "Il PDF è già in fase di generazione per questa squadriglia. "
                             "Riceverai una mail quando sarà pronto."}
    if cache.get(lock_key_massivo(diario.edizione_id)):
        return {"stato": StatoPdf.BLOCCATO, "sincrono": False,
                "messaggio": "Generazione massiva dei PDF in corso per questa edizione. "
                             "Attendi il completamento prima di generare singoli PDF."}
    return {"stato": StatoPdf.DA_GENERARE, "sincrono": False,
            "messaggio": "Il PDF non è ancora stato generato."}


def avvia_generazione_pdf(diario, user) -> tuple[dict, bool]:
    """Avvia il task Celery se serve, rispettando lock singolo e massivo. (stato, avviato).

    Imposta `pdf_task_lock:{pk}` (TTL 30 min) prima di accodare il task e manda la mail
    «in generazione» al richiedente; non fa nulla se il PDF è pronto, già in generazione o bloccato.
    """
    from django.core.cache import cache

    stato = stato_pdf(diario)
    if stato["stato"] != StatoPdf.DA_GENERARE:
        return stato, False
    # add() è atomico: due richieste contemporanee non avviano due task
    if not cache.add(pdf_lock_key(diario.pk), True, PDF_LOCK_TTL):
        return stato_pdf(diario), False

    from apps.exports.tasks import _invia_mail_pdf, task_genera_pdf_diario

    _invia_mail_pdf("diario_pdf_in_generazione", user.pk, diario)
    task_genera_pdf_diario.delay(diario.pk, user.pk)
    nuovo = stato_pdf(diario)
    if nuovo["stato"] == StatoPdf.IN_GENERAZIONE:
        nuovo["messaggio"] = (
            "Il PDF è in fase di generazione. "
            f"Riceverai una mail all'indirizzo {user.email} quando sarà pronto."
        )
    return nuovo, True


def contenuto_pdf_pronto(diario) -> tuple[bytes, str] | None:
    """(byte, nome file) del PDF se pronto: dalla cache Drive o, senza Drive, generato al volo.

    None se non pronto. Una cache corrotta (file rimosso da Drive) viene eliminata e il PDF
    torna «da generare». Gli errori di generazione sincrona si propagano.
    """
    if not diario.edizione.drive_oauth_account:
        from apps.exports.service import genera_pdf_diario

        return genera_pdf_diario(diario, include_relazione=True), nome_pdf(diario)
    cache_file = pdf_in_cache(diario)
    if cache_file is None:
        return None
    try:
        contenuto = scarica_da_drive(diario.edizione, cache_file.drive_file_id)
    except Exception:  # noqa: BLE001 - cache corrotta: si rigenera
        cache_file.delete()
        return None
    return contenuto, cache_file.nome or nome_pdf(diario)
