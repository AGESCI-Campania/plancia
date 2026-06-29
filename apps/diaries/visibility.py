# apps/diaries/visibility.py
"""Logica di visibilità dei diari condivisa tra view web, API e export."""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import QuerySet

from apps.diaries.models import Diario

if TYPE_CHECKING:
    from apps.accounts.models import User


def diari_visibili(user: User, edizione=None) -> QuerySet:
    """Restituisce il QuerySet dei diari visibili all'utente.

    - Admin/Segreteria/Incaricati EG/superuser: tutti i diari.
    - CSQ: solo il proprio diario (filtrato per csq=user.socio).
    - CRP: solo i diari del proprio reparto (filtrati per crp=user.socio).
    - PGV: solo i diari assegnati tramite AssegnazionePGV.
    - Qualunque altro ruolo: nessun diario.

    Se edizione è fornita, filtra ulteriormente per quell'edizione.
    """
    qs = Diario.objects.select_related(
        "edizione",
        "squadriglia__reparto__gruppo__zona",
        "csq", "crp", "anagrafica",
    )
    if edizione is not None:
        qs = qs.filter(edizione=edizione)

    if user.is_superuser or user.is_staff_plancia:
        return qs

    if user.ruolo == "csq" and user.socio:
        return qs.filter(csq=user.socio)

    if user.ruolo == "crp" and user.socio:
        return qs.filter(crp=user.socio)

    if user.ruolo == "pgv":
        from apps.evaluations.models import AssegnazionePGV
        assegnati = AssegnazionePGV.objects.filter(pgv=user).values_list(
            "valutazione__diario_id", flat=True
        )
        return qs.filter(pk__in=assegnati)

    return qs.none()
