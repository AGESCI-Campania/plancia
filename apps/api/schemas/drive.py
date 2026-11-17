from datetime import datetime

from ninja import Schema


class OAuthAvvioInSchema(Schema):
    """`edizione_id`: edizione a cui collegare l'account al ritorno da Google (facoltativa)."""

    edizione_id: int | None = None


class OAuthUrlSchema(Schema):
    url: str


class AccountDriveSchema(Schema):
    email: str
    token_scaduto: bool
    aggiornato_at: datetime


class StatoDriveSchema(Schema):
    oauth_configurato: bool
    account: list[AccountDriveSchema]


class CartellaSchema(Schema):
    id: str
    nome: str


class CartellaCreaInSchema(Schema):
    account: str
    nome: str
    parent_id: str | None = None


class CartellaInfoSchema(Schema):
    id: str
    nome: str
    url: str


class DriveEdizioneSchema(Schema):
    """Configurazione Drive di un'edizione (bloccata quando `cartelle_configurate`)."""

    edizione_id: int
    account: str
    account_collegato: bool
    drive_folder_allegati_id: str
    drive_folder_output_id: str
    cartella_diario_format: str
    cartelle_configurate: bool


class DriveEdizioneInSchema(Schema):
    drive_folder_allegati_id: str = ""
    drive_folder_output_id: str = ""
    cartella_diario_format: str = ""
