# apps/api/permissions.py
"""Helper di permesso usati dai router API.

Le regole di visibilità stanno in `apps.diaries.visibility`, quelle sulle azioni FSM e di
valutazione in `apps.evaluations.actions`, quelle sui diari (moduli, allegati, PDF) in
`apps.diaries.permessi`: qui solo i controlli d'accesso per ruolo.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.diaries.models import Diario


def is_staff_plancia(user: User) -> bool:
    return user.is_staff_plancia or user.is_superuser


def richiedi_ruolo(user: User, *ruoli: str) -> None:
    """403 se il ruolo attivo non è tra `ruoli` (il superuser passa sempre)."""
    from django.core.exceptions import PermissionDenied

    if not (user.is_superuser or user.ruolo in ruoli):
        raise PermissionDenied("Il tuo ruolo non consente questa operazione.")


def richiedi_staff(user: User) -> None:
    """403 se l'utente non è Admin, Segreteria o Incaricato EG."""
    from django.core.exceptions import PermissionDenied

    if not is_staff_plancia(user):
        raise PermissionDenied("Operazione riservata alla gestione della piattaforma.")


def richiedi_admin(user: User) -> None:
    from apps.accounts.models import Ruolo

    richiedi_ruolo(user, Ruolo.ADMIN)


def puo_vedere_diario(user: User, diario: Diario) -> bool:
    """Il diario è tra quelli di `diari_visibili` (unica fonte di verità della visibilità)."""
    from apps.diaries.visibility import diari_visibili

    return diari_visibili(user).filter(pk=diario.pk).exists()


def puo_vedere_valutazione(user: User, diario: Diario) -> bool:
    """La valutazione è visibile solo dopo la pubblicazione, e mai al CSQ."""
    if user.ruolo == "csq":
        return False
    if is_staff_plancia(user):
        return True
    val = getattr(diario, "valutazione", None)
    return bool(val and val.pubblicata)
