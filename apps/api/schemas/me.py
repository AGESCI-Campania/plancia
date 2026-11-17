# apps/api/schemas/me.py
from datetime import date, datetime

from ninja import Schema


class RuoloSchema(Schema):
    chiave: str
    etichetta: str


class MeSchema(Schema):
    id: int
    email: str
    nome_completo: str
    ruolo: RuoloSchema
    ruoli_attivi: list[RuoloSchema]
    is_staff_plancia: bool
    is_superuser: bool


# --- Estensioni Fase 2 (campi opzionali: l'app mobile esistente li ignora) ---


class SocioBreveSchema(Schema):
    """Socio AGESCI collegato all'utente."""

    id: int
    codice_socio: str
    nome: str
    cognome: str
    categoria: str
    categoria_display: str
    gruppo: str | None = None
    zona: str | None = None


class UtenteBreveSchema(Schema):
    id: int
    email: str
    nome_completo: str


class MenuSchema(Schema):
    """Voci di menu della SPA: stesse condizioni della sidebar di `templates/base.html`."""

    puo_vedere_diari: bool
    puo_gestire_edizioni: bool
    puo_vedere_utenti: bool
    puo_gestire_inviti: bool
    puo_gestire_inviti_crp: bool
    puo_importare: bool
    puo_vedere_statistiche: bool
    puo_vedere_impostazioni: bool
    puo_vedere_helpdesk: bool
    puo_gestire_helpdesk: bool
    puo_usare_admin_django: bool


class MeEstesoSchema(Schema):
    """`GET /me`: campi storici + dati per il layout della SPA."""

    id: int
    email: str
    nome_completo: str
    ruolo: RuoloSchema
    ruoli_attivi: list[RuoloSchema]
    is_staff_plancia: bool
    is_superuser: bool
    # nuovi (Fase 2)
    first_name: str = ""
    last_name: str = ""
    socio: SocioBreveSchema | None = None
    mfa_attiva: bool = False
    mfa_richiesta: bool = False
    mfa_da_configurare: bool = False
    menu: MenuSchema | None = None
    impersonato_da: UtenteBreveSchema | None = None
    puo_modificare_email: bool = False
    puo_modificare_nome: bool = False


class ProfiloPatchSchema(Schema):
    """Dati del profilo modificabili dall'utente: email (Capo Squadriglia), nome e cognome
    (senza Socio). I campi omessi non cambiano."""

    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class CambiaRuoloSchema(Schema):
    ruolo: str


class NominaSchema(Schema):
    id: int
    ruolo: RuoloSchema
    attiva: bool
    scaduta: bool
    scadenza: date | None = None
    edizione_id: int | None = None
    edizione: str | None = None
    nominato_da: UtenteBreveSchema | None = None
    da_sso: bool
    creato_at: datetime


class LoginEventSchema(Schema):
    id: int
    creato_at: datetime
    esito: str
    esito_display: str
    ip: str | None = None
    provider: str
    user_agent: str


class SocialAccountSchema(Schema):
    id: int
    provider: str
    nome_provider: str
    uid: str
    email: str | None = None


class ProfiloSchema(Schema):
    """Pagina profilo: dati, storico nomine, ultimi accessi, account social collegati."""

    utente: MeEstesoSchema
    nomine: list[NominaSchema]
    accessi: list[LoginEventSchema]
    social_accounts: list[SocialAccountSchema]


class SessioneSchema(Schema):
    id: int
    ip: str
    user_agent: str
    creato_at: datetime
    ultimo_accesso: datetime
    corrente: bool


class TerminaSessioniRispostaSchema(Schema):
    terminate: int
    detail: str
