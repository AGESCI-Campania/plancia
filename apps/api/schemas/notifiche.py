# apps/api/schemas/notifiche.py
"""Schemi del router `notifiche`: inviti, stato di consegna, attivazione account."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from ninja import Schema


class InvitoSchema(Schema):
    """Un invito con stato e tracking di consegna (popolato dai webhook del provider)."""

    id: int
    ruolo_target: str
    ruolo_target_display: str
    tipo: str
    stato: str
    stato_display: str
    inviato_at: datetime | None
    attivato_at: datetime | None
    delivery_status: str
    delivery_status_display: str
    delivery_error: str
    email_destinatario: str


class PersonaInvitoSchema(Schema):
    """Capo Squadriglia o Capo Reparto di una riga della gestione inviti."""

    socio_id: int
    nome: str
    cognome: str
    email: str | None = None  # None se manca o è un segnaposto interno
    provvisorio: bool = False


class RigaInvitiSchema(Schema):
    """Un diario dell'edizione con l'ultimo invito al Capo Squadriglia e al Capo Reparto."""

    diario_id: int
    squadriglia: str
    reparto: str
    gruppo: str
    zona: str
    csq: PersonaInvitoSchema | None
    crp: PersonaInvitoSchema | None
    ultimo_invito_csq: InvitoSchema | None
    ultimo_invito_crp: InvitoSchema | None
    inviti_reinviabili: list[int]  # id degli inviti in stato "inviato" su questo diario


class EdizioneBreveSchema(Schema):
    id: int
    anno: int
    nome: str


class ContatoriInvitiSchema(Schema):
    capi_totale: int
    capi_inviati: int
    capi_attivati: int
    capi_da_invitare: int
    csq_totale: int
    csq_inviati: int
    csq_attivati: int
    csq_da_invitare: int


class RiepilogoInvitiSchema(Schema):
    """Testata della pagina gestione inviti (edizione attiva, contatori, filtri)."""

    edizione: EdizioneBreveSchema | None
    contatori: ContatoriInvitiSchema | None
    zone: list[str]
    gruppi: list[str]
    backend_massivo_display: str


class InviaInvitiEdizioneIn(Schema):
    tipo: Literal["capi", "csq"]
    backend: Literal["standard", "massivo"] = "massivo"


class InviaInvitiDiarioIn(Schema):
    ruoli: list[Literal["csq", "crp"]] = ["csq", "crp"]


class EsitoSchema(Schema):
    detail: str


class RigaInvitiCrpSchema(Schema):
    diario_id: int
    squadriglia: str
    reparto: str
    csq: PersonaInvitoSchema | None
    ultimo_invito_csq: InvitoSchema | None
    reinviabile: bool


class InvitiCrpSchema(Schema):
    edizione: EdizioneBreveSchema | None
    righe: list[RigaInvitiCrpSchema]


class ReinvioSchema(Schema):
    detail: str
    invito: InvitoSchema


class InvitoPubblicoSchema(Schema):
    """Dati per la pagina di attivazione (pubblica: niente dati personali)."""

    tipo: str
    ruolo_target: str
    ruolo_target_display: str
    stato: str
    attivabile: bool
    richiede_codice_socio: bool
    messaggio: str | None
    squadriglia: str | None
    edizione: str | None


class AttivaInvitoIn(Schema):
    """Solo per gli inviti Capo Squadriglia: codice socio AGESCI ed email di accesso."""

    codice_socio: str = ""
    email: str = ""


class AttivazioneSchema(Schema):
    detail: str
    ruolo: str
    diario_id: int | None
    # False: account con credenziali proprie o di staff, la SPA manda alla pagina di accesso
    login: bool = True
