# apps/api/schemas/evaluations.py
from ninja import Schema


class DiarioStatoSchema(Schema):
    stato: str
    stato_display: str


class AssegnazionePGVApiSchema(Schema):
    pgv_pk: int
    pgv_nome: str
    pgv_email: str


class ValutazioneApiSchema(Schema):
    esito: str | None
    esito_display: str | None
    stato: str
    note: str
    pubblicata: bool
    assegnazioni: list[AssegnazionePGVApiSchema]


class AssegnaPGVBodySchema(Schema):
    pgv_pk: int


class ValutaBodySchema(Schema):
    esito: str
    note: str = ""


class ConfermaBodySchema(Schema):
    note: str = ""


class ActionErrorSchema(Schema):
    detail: str
