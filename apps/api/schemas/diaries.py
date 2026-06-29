# apps/api/schemas/diaries.py
from datetime import date
from typing import Any

from ninja import Schema


class PostoAzioneSchema(Schema):
    id: int
    chi: str
    cosa: str


class PostoAzioneMissioneSchema(Schema):
    descrizione: str


class EsitoSpecialitaSchema(Schema):
    id: int
    tipo: str
    chi: str
    nome: str
    stato: str


class MembroSqSchema(Schema):
    id: int
    nome: str
    ruolo: str
    sentiero: str


class ImpresaSchema(Schema):
    numero: int
    titolo: str
    data_inizio: date | None
    data_fine: date | None
    perche: str
    come: str
    cosa: str
    link_esterno: str
    posti_azione: list[PostoAzioneSchema]
    specialita: list[EsitoSpecialitaSchema]
    brevetti: list[EsitoSpecialitaSchema]


class AnagraficaSchema(Schema):
    squadriglia_nome: str
    tipo_diario: str
    crp_nome: str
    crp_cognome: str
    crp_email: str
    crp_cell: str
    csq_nome: str
    csq_cognome: str
    csq_email: str
    csq_cell: str
    specialita: str
    partecipa_evento: bool
    desc_prima_impresa: str
    desc_seconda_impresa: str
    tecniche: str


class PresentazioneSchema(Schema):
    cosa_sappiamo_fare: str
    membri: list[MembroSqSchema]


class MissioneSchema(Schema):
    titolo: str
    data: date | None
    descrizione_svolgimento: str
    posti_azione: list[PostoAzioneMissioneSchema]


class RelazioneFinaleSchema(Schema):
    sintesi_impresa_1: str
    sintesi_impresa_2: str
    sintesi_missione: str
    considerazioni: str
    specialita_conquistata: bool


class ValutazioneSchema(Schema):
    esito: str | None
    esito_display: str | None
    stato: str
    note: str
    pubblicata: bool


class DiarioListSchema(Schema):
    id: int
    edizione_id: int
    edizione_anno: int
    squadriglia: str
    zona: str
    gruppo: str
    reparto: str
    tipo: str
    tipo_display: str
    stato: str
    stato_display: str
    scadenza: date | None
    pubblicato: bool


class DiarioDetailSchema(Schema):
    id: int
    edizione_id: int
    edizione_anno: int
    squadriglia: str
    zona: str
    gruppo: str
    reparto: str
    tipo: str
    tipo_display: str
    stato: str
    stato_display: str
    scadenza: date | None
    pubblicato: bool
    drive_folder_url: str | None
    anagrafica: AnagraficaSchema | None
    presentazione: PresentazioneSchema | None
    imprese: list[ImpresaSchema]
    missione: MissioneSchema | None
    relazione_finale: RelazioneFinaleSchema | None
    valutazione: ValutazioneSchema | None


# ---------------------------------------------------------------------------
# Schema per le richieste PUT (write moduli)
# ---------------------------------------------------------------------------

class VersionedPutSchema(Schema):
    """Payload generico per PUT con optimistic locking."""
    version: int
    data: dict[str, Any]


class RelazioneFinaleUpdateSchema(Schema):
    """Payload PUT relazione finale (nessun locking — RelazioneFinale non ha version)."""
    data: dict[str, Any]


# ---------------------------------------------------------------------------
# Schema di risposta per le PUT (restituiscono il modulo aggiornato)
# ---------------------------------------------------------------------------

class AnagraficaResponseSchema(Schema):
    version: int
    data: AnagraficaSchema


class PresentazioneResponseSchema(Schema):
    version: int
    data: PresentazioneSchema


class ImpresaResponseSchema(Schema):
    version: int
    data: ImpresaSchema


class MissioneResponseSchema(Schema):
    version: int
    data: MissioneSchema


class RelazioneFinaleResponseSchema(Schema):
    data: RelazioneFinaleSchema


# ---------------------------------------------------------------------------
# Schema di errore
# ---------------------------------------------------------------------------

class ConflictResponseSchema(Schema):
    error: str = "conflict"
    server_version: int


class ValidationErrorResponseSchema(Schema):
    error: str = "validation"
    errors: dict[str, Any]
