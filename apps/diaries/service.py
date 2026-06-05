# apps/diaries/service.py
"""Logica di dominio per i Diari di Bordo."""
from __future__ import annotations

import contextlib
import re
import unicodedata

from apps.editions.models import CARTELLA_DIARIO_FORMAT_DEFAULT

VARIABILI_FORMATO = [
    "{id_univoco}",
    "{edizione}",
    "{nome_gruppo}",
    "{nome_zona}",
    "{nome_reparto}",
    "{nome_squadriglia}",
    "{specialita}",
]

_DUMMY_VALORI = {
    "id_univoco": "00001",
    "edizione": "2026",
    "nome_gruppo": "Gruppo",
    "nome_zona": "Zona",
    "nome_reparto": "Reparto",
    "nome_squadriglia": "Squadriglia",
    "specialita": "Campismo",
}


def valida_formato_cartella(fmt: str) -> str | None:
    """Restituisce il messaggio di errore oppure None se il formato è valido."""
    if not fmt:
        return "Il formato non può essere vuoto."
    if "{id_univoco}" not in fmt:
        return "Il formato deve contenere {id_univoco}."
    try:
        fmt.format(**_DUMMY_VALORI)
    except KeyError as exc:
        return f"Variabile non riconosciuta: {exc}. Usa solo le variabili previste."
    return None


def sanitizza_nome_cartella(s: str) -> str:
    """Rimuove caratteri non validi per nomi cartella Drive/filesystem."""
    # Decomponi e rimuovi diacritici
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Spazi e separatori → underscore
    s = re.sub(r"[\s/\\]+", "_", s)
    # Caratteri vietati su Drive/filesystem → rimossi
    s = re.sub(r'[<>:"|?*\x00-\x1f]', "", s)
    # Underscore ripetuti → uno solo
    s = re.sub(r"_+", "_", s)
    # Tronca a 100 caratteri e rimuovi underscore iniziali/finali
    s = s.strip("_")[:100].strip("_")
    return s or "diario"


def calcola_nome_cartella_diario(diario) -> str:
    """Restituisce il nome sanificato della sottocartella per questo diario."""
    edizione = diario.edizione
    squadriglia = diario.squadriglia
    reparto = squadriglia.reparto
    gruppo = reparto.gruppo
    zona = gruppo.zona

    specialita = ""
    with contextlib.suppress(Exception):
        specialita = diario.anagrafica.specialita or ""

    fmt = edizione.cartella_diario_format or CARTELLA_DIARIO_FORMAT_DEFAULT

    raw = fmt.format(
        id_univoco=f"{diario.pk:05d}",
        edizione=str(edizione.anno),
        nome_gruppo=gruppo.nome,
        nome_zona=zona.nome,
        nome_reparto=reparto.nome,
        nome_squadriglia=squadriglia.nome,
        specialita=specialita,
    )
    return sanitizza_nome_cartella(raw)
