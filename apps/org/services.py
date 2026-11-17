"""Servizi dell'anagrafica: ricerca dei Soci per l'autocompletamento."""
from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.org.models import Socio


def cerca_soci(
    q: str | None = None,
    categoria: str | None = None,
    ruolo: str | None = None,
    limite: int = 20,
) -> QuerySet[Socio]:
    """Soci che corrispondono a `q` (nome, cognome, zona, gruppo o inizio del codice socio).

    `categoria` filtra capo/ragazzo, `ruolo` il ruolo attivo dell'utente collegato.
    """
    qs = Socio.objects.select_related("gruppo", "zona", "utente")
    if categoria:
        qs = qs.filter(categoria=categoria)
    if ruolo:
        qs = qs.filter(utente__ruolo=ruolo)
    q = (q or "").strip()
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(cognome__icontains=q)
            | Q(zona__nome__icontains=q)
            | Q(gruppo__nome__icontains=q)
            | Q(codice_socio__startswith=q)
        )
    return qs[:limite]


def utente_pk(socio: Socio) -> int | None:
    """PK dell'utente collegato al Socio, o None se l'account non esiste ancora."""
    try:
        return socio.utente.pk
    except Socio.utente.RelatedObjectDoesNotExist:
        return None


def etichetta(socio: Socio) -> str:
    return f"{socio.cognome} {socio.nome} - {socio.gruppo.nome} ({socio.zona.nome}) #{socio.codice_socio}"
