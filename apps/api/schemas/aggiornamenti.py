"""Schemi dell'aggiornamento del server dal web (solo Admin)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ninja import Schema


class ReleaseSchema(Schema):
    versione: str
    nome: str
    note: str  # markdown
    pubblicata_at: datetime | None
    url: str
    controllata_at: datetime | None
    errore: str


class RichiestaSchema(Schema):
    id: int
    versione: str
    versione_partenza: str
    richiesta_da: str
    richiesta_at: datetime
    stato: str
    stato_display: str
    fase: str
    messaggio: str
    percentuale: int | None
    log: str
    completato_at: datetime | None

    @staticmethod
    def resolve_richiesta_da(obj) -> str:
        return obj.richiesta_da_email

    @staticmethod
    def resolve_stato_display(obj) -> str:
        return obj.get_stato_display()


class AggiornamentiSchema(Schema):
    installata: str
    ultima: ReleaseSchema | None
    aggiornamento_disponibile: bool
    richiesta_in_corso: RichiestaSchema | None


class RichiestaIn(Schema):
    versione: str


class StatoAggiornamentoSchema(Schema):
    installata: str
    richiesta: RichiestaSchema | None
    stato: dict[str, Any] | None  # contenuto grezzo di stato.json (vedi fase2-aggiornamenti.md)
    in_corso: bool


class RiautenticazioneSchema(Schema):
    detail: str
    riautenticazione_richiesta: bool
    # flussi allauth disponibili per l'utente, es. [{"id": "reauthenticate"},
    # {"id": "mfa_reauthenticate", "types": ["totp", "recovery_codes"]}]
    flussi: list[dict[str, Any]]
