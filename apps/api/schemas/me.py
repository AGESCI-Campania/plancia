# apps/api/schemas/me.py
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
