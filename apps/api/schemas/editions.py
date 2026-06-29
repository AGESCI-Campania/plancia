# apps/api/schemas/editions.py
from datetime import date

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
