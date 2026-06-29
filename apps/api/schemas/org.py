# apps/api/schemas/org.py
from ninja import Schema


class SquadrigliaSchema(Schema):
    id: int
    nome: str


class RepartoSchema(Schema):
    id: int
    nome: str
    squadriglie: list[SquadrigliaSchema]


class GruppoSchema(Schema):
    id: int
    nome: str
    reparti: list[RepartoSchema]


class ZonaSchema(Schema):
    id: int
    nome: str
    gruppi: list[GruppoSchema]
