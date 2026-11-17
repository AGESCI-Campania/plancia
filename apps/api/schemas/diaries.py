# apps/api/schemas/diaries.py
from datetime import date, datetime
from typing import Any

from ninja import Schema


class PostoAzioneSchema(Schema):
    id: int
    chi: str
    cosa: str


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


class RelazioneFinaleSchema(Schema):
    sintesi_impresa_1: str
    sintesi_impresa_2: str
    sintesi_missione: str
    considerazioni: str
    specialita_conquistata: bool | None


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
    """Payload PUT relazione finale. `version` facoltativa (compatibilità app mobile):
    se presente si applica l'optimistic locking con 409 come per gli altri moduli."""
    version: int | None = None
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
    version: int | None = None
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


# ---------------------------------------------------------------------------
# Fase 2: lista con filtri, dettaglio esteso, permessi calcolati, allegati, PDF, referenti
# ---------------------------------------------------------------------------

class ReferenteSchema(Schema):
    """Capo Squadriglia o Capo Reparto referente del diario (Socio)."""
    id: int
    nome: str
    cognome: str


class OpzioneSchema(Schema):
    id: int
    nome: str


class SceltaSchema(Schema):
    valore: str
    etichetta: str


class FiltriDiariSchema(Schema):
    """Valori disponibili per i filtri della lista (calcolati sui diari visibili)."""
    edizioni: list[OpzioneSchema]
    zone: list[OpzioneSchema]
    gruppi: list[OpzioneSchema]
    reparti: list[OpzioneSchema]
    specialita: list[str]
    stati: list[SceltaSchema]
    tipi: list[SceltaSchema]
    ordinamenti: list[str]


class OpzioniModuliDiarioSchema(Schema):
    """Scelte dei campi dei moduli 1–5 e limiti delle foto (per i form della SPA)."""
    tipi_diario: list[SceltaSchema]
    specialita_squadriglia: list[str]
    specialita_individuali: list[str]
    brevetti: list[str]
    ruoli_squadriglia: list[SceltaSchema]
    sentieri: list[SceltaSchema]
    stati_specialita: list[SceltaSchema]
    moduli_foto: list[SceltaSchema]
    allegati_max_px: int
    allegati_max_mb: int
    allegati_tipi: list[str]


class PermessiDiarioSchema(Schema):
    """Cosa può fare l'utente corrente sul diario: sempre calcolato dalle regole backend
    (`apps.diaries.permessi`, `apps.evaluations.actions`). Solo per l'interfaccia: ogni
    endpoint ricontrolla."""
    puo_modificare_moduli: bool
    puo_vedere_relazione: bool
    puo_modificare_relazione: bool
    puo_vedere_valutazione: bool
    puo_inviare_csq: bool
    puo_inviare: bool
    puo_riaprire: bool
    puo_cambiare_csq: bool
    puo_cambiare_crp: bool
    puo_concedere_dilazione: bool
    puo_caricare_allegati: bool
    puo_eliminare_allegati: bool
    puo_pdf: bool


class StatoModuliSchema(Schema):
    """Presenza dei moduli e loro versione (0 = non ancora salvato)."""
    anagrafica: bool
    presentazione: bool
    impresa_1: bool
    impresa_2: bool
    missione: bool
    relazione_finale: bool | None  # None se non visibile all'utente
    moduli_csq_completi: bool
    impresa_2_obbligatoria: bool
    missione_obbligatoria: bool
    versioni: dict[str, int]


class ScadenzeSchema(Schema):
    riferimento: str
    riferimento_display: str
    effettiva: date | None
    evento: date | None
    assemblea: date | None
    dilazionata: bool
    seconda_scadenza_passata: bool


class AllegatoSchema(Schema):
    id: int
    modulo: str
    nome: str
    mime: str
    dimensione: int
    stato_sync: str
    creato_at: datetime
    anteprima_url: str
    miniatura_url: str
    download_url: str


class DiarioListaSchema(DiarioListSchema):
    """Riga della lista: i campi di `DiarioListSchema` (app mobile) più quelli della tabella web."""
    zona_id: int | None = None
    gruppo_id: int | None = None
    reparto_id: int | None = None
    specialita: str = ""
    csq: ReferenteSchema | None = None
    crp: ReferenteSchema | None = None
    puo_pdf: bool = False

    # Risolutori: la lista restituisce un QuerySet paginato (niente costruzione in memoria)
    @staticmethod
    def resolve_edizione_anno(obj) -> int:
        return obj.edizione.anno

    @staticmethod
    def resolve_squadriglia(obj) -> str:
        return obj.squadriglia.nome

    @staticmethod
    def resolve_zona(obj) -> str:
        return obj.squadriglia.reparto.gruppo.zona.nome

    @staticmethod
    def resolve_zona_id(obj) -> int:
        return obj.squadriglia.reparto.gruppo.zona_id

    @staticmethod
    def resolve_gruppo(obj) -> str:
        return obj.squadriglia.reparto.gruppo.nome

    @staticmethod
    def resolve_gruppo_id(obj) -> int:
        return obj.squadriglia.reparto.gruppo_id

    @staticmethod
    def resolve_reparto(obj) -> str:
        return obj.squadriglia.reparto.nome

    @staticmethod
    def resolve_reparto_id(obj) -> int:
        return obj.squadriglia.reparto_id

    @staticmethod
    def resolve_tipo_display(obj) -> str:
        return obj.get_tipo_display()

    @staticmethod
    def resolve_stato_display(obj) -> str:
        return obj.get_stato_display()

    @staticmethod
    def resolve_scadenza(obj):
        return obj.scadenza_effettiva()

    @staticmethod
    def resolve_specialita(obj) -> str:
        ana = getattr(obj, "anagrafica", None)
        return (ana.specialita if ana else "") or ""

    @staticmethod
    def resolve_csq(obj):
        s = obj.csq
        return {"id": s.pk, "nome": s.nome, "cognome": s.cognome} if s else None

    @staticmethod
    def resolve_crp(obj):
        s = obj.crp
        return {"id": s.pk, "nome": s.nome, "cognome": s.cognome} if s else None

    @staticmethod
    def resolve_puo_pdf(obj, context) -> bool:
        from apps.diaries import permessi

        user = context["request"].auth
        return permessi.puo_scaricare_pdf(user) and permessi.pdf_disponibile_nello_stato(obj)


class DiarioDettaglioSchema(DiarioDetailSchema):
    """Dettaglio: i campi di `DiarioDetailSchema` (app mobile) più stato moduli, scadenze,
    referenti, allegati e permessi calcolati."""
    squadriglia_id: int | None = None
    reparto_id: int | None = None
    csq: ReferenteSchema | None = None
    crp: ReferenteSchema | None = None
    scadenze: ScadenzeSchema | None = None
    stato_moduli: StatoModuliSchema | None = None
    permessi: PermessiDiarioSchema | None = None
    allegati: list[AllegatoSchema] = []
    inviato_at: datetime | None = None
    csq_completato_at: datetime | None = None
    aggiornato_at: datetime | None = None


class DiarioStatoLeggeroSchema(Schema):
    """Equivalente di `GET /api/diari/<pk>/` della PWA (stato per la compilazione offline)."""
    stato: str
    stato_display: str
    tipo: str
    puo_editare: bool
    moduli_csq_completi: bool
    has_anagrafica: bool
    has_presentazione: bool
    imprese: list[int]
    has_missione: bool
    versioni: dict[str, int]


class AnagraficaModuloSchema(Schema):
    version: int
    data: AnagraficaSchema


class PresentazioneModuloSchema(Schema):
    version: int
    data: PresentazioneSchema


class ImpresaModuloSchema(Schema):
    version: int
    data: ImpresaSchema


class MissioneModuloSchema(Schema):
    version: int
    data: MissioneSchema


class RelazioneFinaleModuloSchema(Schema):
    version: int
    data: RelazioneFinaleSchema


class CambioReferenteBodySchema(Schema):
    socio_id: int


class CambioReferenteRispostaSchema(Schema):
    detail: str
    nuovo: ReferenteSchema
    precedente: ReferenteSchema | None


class DiarioRepartoSchema(Schema):
    id: int
    edizione_anno: int
    squadriglia: str
    stato: str
    stato_display: str
    csq: ReferenteSchema | None
    crp: ReferenteSchema | None


class RepartoDiariSchema(Schema):
    reparto: OpzioneSchema
    diari: list[DiarioRepartoSchema]


class CambioCrpRepartoRispostaSchema(Schema):
    detail: str
    nuovo: ReferenteSchema
    diari_aggiornati: int


class PdfStatoSchema(Schema):
    """Stato del PDF del diario: `pronto` | `da_generare` | `in_generazione` | `bloccato`."""
    stato: str
    messaggio: str
    sincrono: bool
    avviato: bool = False
    download_url: str | None = None
