# apps/api/permissions.py
"""Helper di permesso usati dai router API.

Replicano le regole di visibilità delle view web — non delegano a quelle view.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.diaries.models import Diario


def is_staff_plancia(user: User) -> bool:
    return user.is_staff_plancia or user.is_superuser


def puo_vedere_diario(user: User, diario: Diario) -> bool:
    """Replica la logica di EdizioneDetailView._diari_visibili."""
    if is_staff_plancia(user):
        return True
    if user.ruolo == "pgv":
        return True
    if user.ruolo == "crp" and user.socio:
        return diario.crp_id == user.socio.pk
    if user.ruolo == "csq" and user.socio:
        return diario.csq_id == user.socio.pk
    return False


def puo_editare_diario(user: User, diario: Diario) -> bool:
    """Replica _puo_editare dei moduli CSQ: stato ∈ {NON_INIZIATO, IN_COMPILAZIONE} e ruolo CSQ."""
    from apps.diaries.models import StatoDiario

    if user.ruolo != "csq" or not user.socio:
        return False
    if diario.csq_id != user.socio.pk:
        return False
    return diario.stato in (StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE)


def puo_editare_relazione_finale(user: User, diario: Diario) -> bool:
    from apps.diaries.models import StatoDiario

    if user.ruolo != "crp" or not user.socio:
        return False
    if diario.crp_id != user.socio.pk:
        return False
    return diario.stato == StatoDiario.RELAZIONE_FINALE


def puo_vedere_valutazione(user: User, diario: Diario) -> bool:
    """La valutazione è visibile solo dopo la pubblicazione, e mai al CSQ."""
    if user.ruolo == "csq":
        return False
    if is_staff_plancia(user):
        return True
    val = getattr(diario, "valutazione", None)
    return bool(val and val.pubblicata)
