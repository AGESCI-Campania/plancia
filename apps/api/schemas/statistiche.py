"""Schemi della dashboard statistiche (dati grezzi: i grafici li disegna la SPA)."""
from __future__ import annotations

from ninja import Schema


class EdizioneBreveSchema(Schema):
    id: int
    anno: int
    stato: str


class ZonaBreveSchema(Schema):
    id: int
    nome: str


class StatZonaSchema(Schema):
    zona: ZonaBreveSchema
    totale: int
    approvati: int
    non_approvati: int
    maggiori_info: int
    pubblicati: int
    percentuale_approvati: int


class StatGlobaliSchema(Schema):
    totale: int
    inviati: int
    approvati: int
    non_approvati: int
    in_compilazione: int
    pubblicati: int


class StatCategoriaSchema(Schema):
    chiave: str
    categoria: str
    count: int


class StatTicketSchema(Schema):
    totale: int
    aperti: int
    chiusi: int
    per_categoria: list[StatCategoriaSchema]


class StatisticheSchema(Schema):
    edizioni: list[EdizioneBreveSchema]
    edizione: EdizioneBreveSchema | None
    per_zona: list[StatZonaSchema]
    globali: StatGlobaliSchema | None
    ticket: StatTicketSchema | None
