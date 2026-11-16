from datetime import datetime

from ninja import Schema


class DiarioStatoSchema(Schema):
    stato: str
    stato_display: str


class AssegnazionePGVApiSchema(Schema):
    pgv_pk: int
    pgv_nome: str
    pgv_email: str


class AzioniValutazioneSchema(Schema):
    """Azioni che il ruolo attivo può tentare (indicazione per l'interfaccia: il backend
    ricontrolla sempre permessi e stato)."""

    puo_valutare_direttamente: bool
    puo_proporre: bool
    puo_confermare: bool
    puo_rigettare: bool
    puo_modificare: bool
    puo_pubblicare: bool
    puo_assegnare_pgv: bool


class ValutazioneApiSchema(Schema):
    esito: str | None
    esito_display: str | None
    stato: str
    note: str
    pubblicata: bool
    assegnazioni: list[AssegnazionePGVApiSchema]
    # Campi aggiunti in Fase 2 (opzionali)
    stato_display: str | None = None
    proposta_esito: str | None = None
    proposta_esito_display: str | None = None
    valutatore: str | None = None
    confermata_da: str | None = None
    aggiornata_at: datetime | None = None
    diario_stato: str | None = None
    azioni: AzioniValutazioneSchema | None = None


class AssegnaPGVBodySchema(Schema):
    pgv_pk: int


class ValutaBodySchema(Schema):
    esito: str
    note: str = ""


class ConfermaBodySchema(Schema):
    note: str = ""


class ActionErrorSchema(Schema):
    detail: str
