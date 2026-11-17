from datetime import date, datetime

from ninja import Schema


class EdizioneSchema(Schema):
    id: int
    anno: int
    stato: str
    stato_display: str
    scadenza_evento: date | None
    scadenza_assemblea: date | None
    data_evento_inizio: date | None
    data_evento_fine: date | None
    evento_comune: str
    # Campi aggiunti in Fase 2 (opzionali: l'app mobile non li usa)
    evento_localita: str = ""
    scadenza_corrente: str | None = None
    seconda_scadenza_passata: bool | None = None
    cartelle_configurate: bool | None = None


class EdizioneInSchema(Schema):
    """Corpo di creazione/modifica edizione (in PATCH tutti i campi sono facoltativi)."""

    anno: int | None = None
    stato: str | None = None
    scadenza_evento: date | None = None
    scadenza_assemblea: date | None = None
    data_evento_inizio: date | None = None
    data_evento_fine: date | None = None
    evento_comune: str | None = None
    evento_localita: str | None = None


class StatoConteggioSchema(Schema):
    stato: str
    label: str
    totale: int
    percentuale: int


class StatsDiariSchema(Schema):
    totale: int
    per_stato: list[StatoConteggioSchema]


class FiltriRiepilogoSchema(Schema):
    """Valori distinti dei diari visibili, per i filtri dell'elenco."""

    zone: list[str]
    gruppi: list[str]
    specialita: list[str]


class RiepilogoEdizioneSchema(Schema):
    edizione: EdizioneSchema
    puo_gestire: bool
    totale_diari: int
    #: Incaricato EG / Admin: pubblicazione di tutti gli esiti confermati
    puo_pubblicare_esiti: bool = False
    stats_diari: StatsDiariSchema | None = None
    filtri: FiltriRiepilogoSchema


class EdizioneAttivaSchema(Schema):
    """Home: riepilogo dell'edizione attiva, o `null` se non ce n'è una aperta/in valutazione."""

    riepilogo: RiepilogoEdizioneSchema | None
    puo_gestire: bool


class DilazioneInSchema(Schema):
    diario_id: int
    nuova_scadenza: date
    motivazione: str


class DilazioneSchema(Schema):
    id: int
    diario_id: int
    squadriglia: str
    nuova_scadenza: date
    motivazione: str
    concessa_da: str | None
    creata_at: datetime


class PubblicaEsitiSchema(Schema):
    pubblicati: int


class ExportAvviatoSchema(Schema):
    """Export in preparazione (task Celery): il file arriverà via email."""

    detail: str
    formato: str
    diari: int
