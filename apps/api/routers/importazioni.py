"""Importazioni: lancio per tracciato, storico log, anomalie, scarti, riconciliazione.

Riservato a Admin, Segreteria e Incaricati EG (come le viste web `apps/imports/views.py`).
Logica in `apps.imports.services`.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from ninja import File, Form, Router, Status
from ninja.files import UploadedFile
from ninja.pagination import LimitOffsetPagination, paginate

from apps.accounts.models import Ruolo
from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.permissions import richiedi_ruolo
from apps.api.schemas.importazioni import (
    LancioImportSchema,
    LogImportazioneDettaglioSchema,
    LogImportazioneSchema,
    RiconciliaIn,
    RiconciliaOut,
    RiprovaOut,
    TracciatoSchema,
)
from apps.imports import services
from apps.imports.models import LogImportazione, RigaImportazione, TipoImport

router = Router(tags=["importazioni"])

_STAFF = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)
_ERRORI = {401: ErroreSchema, 403: ErroreSchema, 404: ErroreSchema, 422: ErroreValidazioneSchema}


def _richiedi_staff(request) -> None:
    richiedi_ruolo(request.auth, *_STAFF)


def _log(log_id: int) -> LogImportazione:
    return get_object_or_404(
        LogImportazione.objects.select_related("edizione", "creato_da"), pk=log_id
    )


@router.get("/tracciati", response={200: list[TracciatoSchema], **_ERRORI},
            summary="Tracciati di import disponibili")
def tracciati(request):
    _richiedi_staff(request)
    return [
        TracciatoSchema(chiave=k, etichetta=et, estensione=ext, edizione_obbligatoria=obbl)
        for k, (et, ext, obbl) in services.TRACCIATI.items()
    ]


@router.post("/lancia/{tracciato}", response={202: LancioImportSchema, **_ERRORI},
             summary="Carica un file e avvia l'import del tracciato")
def lancia(
    request,
    tracciato: str,
    file: File[UploadedFile] = None,  # type: ignore[assignment]
    edizione_pk: Form[str] = None,  # type: ignore[assignment]
):
    """`multipart/form-data` con `file` e, per `squadriglie` (obbligatoria) e `risposte_eg`
    (facoltativa), `edizione_pk`. L'import gira in Celery: `coca`, `ragazzi` e `squadriglie`
    producono un log nello storico, `risposte_eg` invia l'esito per email agli Admin."""
    _richiedi_staff(request)
    esito = services.lancia_import(tracciato, file, edizione_pk)
    return Status(202, LancioImportSchema(
        tracciato=esito.tracciato, task_id=esito.task_id, messaggio=esito.messaggio
    ))


@router.get("/log", response={200: list[LogImportazioneSchema], **_ERRORI},
            summary="Storico delle importazioni")
@paginate(LimitOffsetPagination)
def lista_log(request, tipo: str | None = None):
    _richiedi_staff(request)
    qs = LogImportazione.objects.select_related("edizione", "creato_da").order_by("-creato_at")
    if tipo in TipoImport.values:
        qs = qs.filter(tipo=tipo)
    return qs


@router.get("/log/{log_id}", response={200: LogImportazioneDettaglioSchema, **_ERRORI},
            summary="Dettaglio di un import: righe da riconciliare e scartate")
def dettaglio_log(request, log_id: int):
    _richiedi_staff(request)
    return _log(log_id)


@router.get("/log/{log_id}/scarti.csv", response={200: None, **_ERRORI},
            summary="Scarica le righe scartate (CSV UTF-8 con BOM)")
def scarti_csv(request, log_id: int):
    _richiedi_staff(request)
    log = get_object_or_404(LogImportazione, pk=log_id)
    response = HttpResponse(services.csv_scarti(log), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="scarti_import_{log.pk}.csv"'
    return response


@router.post("/righe/{riga_id}/riconcilia", response={200: RiconciliaOut, **_ERRORI},
             summary="Associa a mano una riga da riconciliare a un Socio capo")
def riconcilia(request, riga_id: int, dati: RiconciliaIn):
    _richiedi_staff(request)
    from apps.org.models import Socio

    riga = get_object_or_404(RigaImportazione.objects.select_related("log"), pk=riga_id)
    socio = Socio.objects.filter(pk=dati.socio_pk).first()
    if socio is None:
        raise ValidationError({"socio_pk": ["Socio inesistente."]})
    services.riconcilia_riga(riga, socio)
    riga.refresh_from_db()
    return {
        "messaggio": f"Riga {riga.numero} riconciliata con {socio}.",
        "riga": riga, "log": _log(riga.log_id),
    }


@router.post("/log/{log_id}/riprova", response={200: RiprovaOut, **_ERRORI},
             summary="Riprova ad abbinare i Capi Reparto delle anomalie (import squadriglie)")
def riprova(request, log_id: int):
    _richiedi_staff(request)
    log = _log(log_id)
    risolte, aperte = services.riprova_anomalie(log)
    return {
        "messaggio": services.messaggio_riprova(risolte, aperte),
        "risolte": risolte, "ancora_aperte": aperte, "log": _log(log_id),
    }
