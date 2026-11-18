"""Servizi delle importazioni: lancio per tracciato, scarti, riconciliazione.

Usati dal router API `apps/api/routers/importazioni.py` e dai comandi `import_*`.
Vedi docs sez. 14.
"""
from __future__ import annotations

import csv
import io
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import get_valid_filename

from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch, TipoImport

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from apps.org.models import Socio

# Tracciati accettati dal lancio: chiave → (etichetta, estensione attesa, edizione obbligatoria)
TRACCIATI: dict[str, tuple[str, str, bool]] = {
    "coca": ("Capi (Co.Ca.)", ".csv", False),
    "ragazzi": ("Ragazzi", ".csv", False),
    "squadriglie": ("Squadriglie iscritte", ".csv", True),
    "risposte_eg": ("Risposte EG (Jotform)", ".xlsx", False),
}


@dataclass
class EsitoLancio:
    tracciato: str
    task_id: str
    messaggio: str


def salva_file_caricato(file_obj: UploadedFile) -> str:
    """Salva il file caricato in MEDIA_ROOT/imports/tmp/ e restituisce il percorso."""
    tmp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    nome_sicuro = get_valid_filename(file_obj.name or "import")
    path = os.path.join(tmp_dir, f"{int(time.time())}_{nome_sicuro}")
    with open(path, "wb") as f:
        for chunk in file_obj.chunks():
            f.write(chunk)
    return path


def _edizione_pk(valore) -> int | None:
    try:
        return int(valore) or None
    except (TypeError, ValueError):
        return None


def lancia_import(tracciato: str, file_obj: UploadedFile | None, edizione_pk=None) -> EsitoLancio:
    """Salva il file e accoda il task Celery del tracciato.

    Solleva `ValidationError` (per campo) se tracciato, file o edizione non sono validi.
    `risposte_eg` è asincrono con email agli Admin; gli altri scrivono un `LogImportazione`.
    """
    if tracciato not in TRACCIATI:
        raise ValidationError({"tracciato": ["Tracciato non valido."]})
    if not file_obj:
        raise ValidationError({"file": ["Seleziona un file prima di avviare l'import."]})
    etichetta, estensione, edizione_obbligatoria = TRACCIATI[tracciato]
    if not (file_obj.name or "").lower().endswith(estensione):
        raise ValidationError({"file": [f"Il file deve essere in formato {estensione}."]})
    pk = _edizione_pk(edizione_pk)
    if edizione_obbligatoria and not pk:
        raise ValidationError(
            {"edizione_pk": ["Seleziona un'edizione per l'import squadriglie iscritte."]}
        )
    if pk is not None:
        from apps.editions.models import Edizione

        if not Edizione.objects.filter(pk=pk).exists():
            raise ValidationError({"edizione_pk": ["Edizione inesistente."]})

    path = salva_file_caricato(file_obj)

    if tracciato == "risposte_eg":
        from apps.imports.tasks import task_import_risposte_eg

        res = task_import_risposte_eg.delay(path, edizione_pk=pk)
        return EsitoLancio(
            tracciato, str(res.id),
            "Import Risposte EG avviato in background. "
            "Gli amministratori riceveranno una mail con i risultati al termine.",
        )

    from apps.imports.tasks import task_lancia_import

    res = task_lancia_import.delay(tracciato, path=path, edizione_pk=pk)
    return EsitoLancio(
        tracciato, str(res.id),
        f"Import «{etichetta}» avviato. Controlla lo storico per l'esito.",
    )


def csv_scarti(log: LogImportazione) -> str:
    """Le righe scartate del log come CSV (UTF-8 con BOM per Excel)."""
    righe = list(log.righe.filter(stato_match=StatoMatch.SCARTATA).order_by("numero"))
    buf = io.StringIO()
    buf.write("﻿")  # BOM UTF-8 per Excel
    if righe:
        fieldnames = ["#", "Errore", *righe[0].dati_grezzi.keys()]
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for riga in righe:
            writer.writerow({"#": riga.numero, "Errore": riga.note, **riga.dati_grezzi})
    return buf.getvalue()


@transaction.atomic
def riconcilia_riga(riga: RigaImportazione, socio: Socio) -> None:
    """Associa a mano una riga `da_riconciliare` al Socio capo corretto e aggiorna i contatori."""
    from apps.org.models import Categoria

    if riga.stato_match != StatoMatch.DA_RICONCILIARE:
        raise ValidationError({"__all__": ["La riga non è da riconciliare."]})
    if socio.categoria != Categoria.CAPO:
        raise ValidationError({"socio_pk": ["Seleziona un Socio capo."]})

    aggiorna_diario_crp(riga, socio)

    riga.socio_match = socio
    riga.stato_match = StatoMatch.OK
    riga.note = f"Riconciliato manualmente → {socio}"
    riga.save(update_fields=["socio_match", "stato_match", "note"])

    log = riga.log
    log.da_riconciliare = max(0, (log.da_riconciliare or 0) - 1)
    log.ok = (log.ok or 0) + 1
    log.save(update_fields=["da_riconciliare", "ok"])


@transaction.atomic
def riprova_anomalie(log: LogImportazione) -> tuple[int, int]:
    """Riprova ad abbinare i Capi Reparto delle righe `da_riconciliare` di un log squadriglie.

    Cerca per email/nome tra i Socio capo NON provvisori presenti ora nel DB, senza
    re-importare il file. Restituisce (risolte, ancora_aperte).
    """
    if log.tipo != TipoImport.SQUADRIGLIE:
        raise ValidationError({"__all__": ["Solo i log delle squadriglie iscritte hanno anomalie."]})

    from apps.imports.management.commands.import_squadriglie import _parse_crp_nome, trova_crp

    risolte = 0
    ancora_aperte = 0
    for riga in log.righe.filter(stato_match=StatoMatch.DA_RICONCILIARE):
        dati = riga.dati_grezzi
        crp_email = (dati.get("EmailReferente") or "").strip()
        crp_raw = (dati.get("NomeReferente") or "").strip()
        crp_cognome, crp_nome = _parse_crp_nome(crp_raw) if crp_raw else ("", "")

        crp_socio, trovato = trova_crp(crp_email, crp_cognome, crp_nome)
        if trovato and getattr(crp_socio, "provvisorio", False):
            trovato = False
            crp_socio = None
        if trovato:
            aggiorna_diario_crp(riga, crp_socio)
            riga.socio_match = crp_socio
            riga.stato_match = StatoMatch.OK
            riga.note = f"Riconciliato automaticamente (riprova) → {crp_socio}"
            riga.save(update_fields=["socio_match", "stato_match", "note"])
            risolte += 1
        else:
            ancora_aperte += 1

    if risolte or ancora_aperte:
        log.da_riconciliare = ancora_aperte
        log.ok = (log.ok or 0) + risolte
        log.save(update_fields=["da_riconciliare", "ok"])
    return risolte, ancora_aperte


def messaggio_riprova(risolte: int, ancora_aperte: int) -> str:
    if not risolte and not ancora_aperte:
        return "Nessuna anomalia da riprovare."
    if risolte:
        return f"Risolte {risolte} anomali{'a' if risolte == 1 else 'e'}." + (
            f" Ne restano {ancora_aperte} da riconciliare manualmente." if ancora_aperte else ""
        )
    return (
        f"Nessuna anomalia risolta. I {ancora_aperte} Capi Reparto non sono ancora presenti nel DB. "
        "Eseguire l'import capi o inserire i capi mancanti, poi riprovare."
    )


def aggiorna_diario_crp(riga: RigaImportazione, crp_socio) -> None:
    """Sostituisce il Capo Reparto sul Diario della riga con il Socio capo reale.

    Gestisce sia il Diario con crp=None sia quello con crp provvisorio (creato durante
    l'import): trasferisce l'eventuale User dal provvisorio al reale e cancella il provvisorio.
    """
    log = riga.log
    if not log.edizione_id:
        return
    codice_csq = (riga.dati_grezzi.get("Codice") or "").strip()
    if not codice_csq:
        return

    from django.db.models import Q

    from apps.diaries.models import Diario
    from apps.org.models import Socio

    csq = Socio.objects.filter(codice_socio=codice_csq).first()
    if not csq:
        return

    diari_da_aggiornare = Diario.objects.filter(edizione_id=log.edizione_id, csq=csq).filter(
        Q(crp__isnull=True) | Q(crp__provvisorio=True)
    )
    provvisori = list(
        Socio.objects.filter(provvisorio=True, diari_crp__in=diari_da_aggiornare).distinct()
    )
    diari_da_aggiornare.update(crp=crp_socio)
    for prov in provvisori:
        trasferisci_utente_provvisorio(prov, crp_socio)


def trasferisci_utente_provvisorio(provvisorio, reale) -> None:
    """Sposta l'account utente dal Socio provvisorio a quello reale, poi elimina il provvisorio."""
    if hasattr(provvisorio, "utente") and provvisorio.utente is not None:
        utente = provvisorio.utente
        utente.socio = reale
        utente.save(update_fields=["socio"])
    provvisorio.delete()
