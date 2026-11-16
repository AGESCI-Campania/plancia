"""Schemi delle importazioni (log, righe, lancio).

I campi calcolati usano i resolver di ninja: ai router si passano i modelli, non dict.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ninja import Schema


class TracciatoSchema(Schema):
    chiave: str
    etichetta: str
    estensione: str
    edizione_obbligatoria: bool


class LancioImportSchema(Schema):
    tracciato: str
    task_id: str
    messaggio: str


class LogImportazioneSchema(Schema):
    id: int
    tipo: str
    tipo_display: str
    file_nome: str
    edizione_id: int | None
    edizione_anno: int | None
    creato_da: str | None
    creato_at: datetime
    totale: int
    ok: int
    scartati: int
    da_riconciliare: int

    @staticmethod
    def resolve_tipo_display(obj) -> str:
        return obj.get_tipo_display()

    @staticmethod
    def resolve_edizione_anno(obj) -> int | None:
        return obj.edizione.anno if obj.edizione_id else None

    @staticmethod
    def resolve_creato_da(obj) -> str | None:
        return obj.creato_da.email if obj.creato_da_id else None


class SocioMatchSchema(Schema):
    id: int
    codice_socio: str
    nome: str
    cognome: str


class RigaImportazioneSchema(Schema):
    id: int
    numero: int
    stato_match: str
    stato_match_display: str
    dati_grezzi: dict[str, Any]
    socio_match: SocioMatchSchema | None
    note: str

    @staticmethod
    def resolve_stato_match_display(obj) -> str:
        return obj.get_stato_match_display()


class LogImportazioneDettaglioSchema(LogImportazioneSchema):
    e_squadriglie: bool
    righe_da_riconciliare: list[RigaImportazioneSchema]
    righe_scartate: list[RigaImportazioneSchema]

    @staticmethod
    def resolve_e_squadriglie(obj) -> bool:
        from apps.imports.models import TipoImport

        return obj.tipo == TipoImport.SQUADRIGLIE

    @staticmethod
    def resolve_righe_da_riconciliare(obj) -> list:
        from apps.imports.models import StatoMatch

        return list(obj.righe.select_related("socio_match")
                    .filter(stato_match=StatoMatch.DA_RICONCILIARE).order_by("numero"))

    @staticmethod
    def resolve_righe_scartate(obj) -> list:
        from apps.imports.models import StatoMatch

        return list(obj.righe.select_related("socio_match")
                    .filter(stato_match=StatoMatch.SCARTATA).order_by("numero"))


class RiconciliaIn(Schema):
    socio_pk: int


class RiconciliaOut(Schema):
    messaggio: str
    riga: RigaImportazioneSchema
    log: LogImportazioneSchema


class RiprovaOut(Schema):
    messaggio: str
    risolte: int
    ancora_aperte: int
    log: LogImportazioneSchema
