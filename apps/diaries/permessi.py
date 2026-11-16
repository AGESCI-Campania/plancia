"""Regole di permesso sul singolo Diario (moduli, allegati, PDF, referenti).

Unica fonte di verità usata dalle viste web, dall'API `/api/v1/diari` e dagli endpoint PWA.
La *visibilità* (chi vede quale diario) sta in `apps.diaries.visibility.diari_visibili`; le
transizioni FSM e la valutazione in `apps.evaluations.actions`: qui solo cosa può fare un
utente su un diario che già vede.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from apps.accounts.models import Ruolo
from apps.diaries.models import StatoDiario

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.diaries.models import Diario

# Stati in cui il diario non è ancora stato inviato allo staff
STATI_PRIMA_INVIO = (
    StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE, StatoDiario.RELAZIONE_FINALE,
)

# Stati in cui il Capo Squadriglia compila i moduli 1–5
STATI_COMPILAZIONE = (StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE)

# Stati in cui ha senso generare il PDF (il Capo Reparto ha inviato il diario)
STATI_PDF = (
    StatoDiario.INVIATO, StatoDiario.IN_VALUTAZIONE, StatoDiario.IN_REVISIONE,
    StatoDiario.APPROVATO, StatoDiario.NON_APPROVATO, StatoDiario.MAGGIORI_INFO,
)


def _is_staff(user: User) -> bool:
    return bool(user.is_superuser or user.is_staff_plancia)


def is_csq_del_diario(user: User, diario: Diario) -> bool:
    return (
        user.ruolo == Ruolo.CSQ and user.socio_id is not None and diario.csq_id == user.socio_id
    )


def is_crp_del_diario(user: User, diario: Diario) -> bool:
    return (
        user.ruolo == Ruolo.CRP and user.socio_id is not None and diario.crp_id == user.socio_id
    )


def puo_modificare_moduli(user: User, diario: Diario) -> bool:
    """Moduli 1–5: staff sempre; il Capo Squadriglia del diario finché è in compilazione."""
    if _is_staff(user):
        return True
    return is_csq_del_diario(user, diario) and diario.stato in STATI_COMPILAZIONE


def puo_vedere_relazione(user: User) -> bool:
    """La relazione finale (modulo 6) non è mai visibile al Capo Squadriglia."""
    return user.ruolo != Ruolo.CSQ


def puo_modificare_relazione(user: User, diario: Diario) -> bool:
    """Modulo 6: staff sempre; il Capo Reparto del diario solo in RELAZIONE_FINALE."""
    if _is_staff(user):
        return True
    return is_crp_del_diario(user, diario) and diario.stato == StatoDiario.RELAZIONE_FINALE


def puo_inviare_csq(user: User, diario: Diario) -> bool:
    """Pulsante «Invia» del Capo Squadriglia (→ RELAZIONE_FINALE): la regola è in `actions.csq_invia`."""
    return (
        diario.stato == StatoDiario.IN_COMPILAZIONE
        and diario.moduli_csq_completi
        and (_is_staff(user) or is_csq_del_diario(user, diario))
    )


def puo_inviare(user: User, diario: Diario) -> bool:
    """Pulsante «Invia allo staff» del Capo Reparto (→ INVIATO): la regola è in `actions.invia`."""
    return diario.stato == StatoDiario.RELAZIONE_FINALE and (
        _is_staff(user) or is_crp_del_diario(user, diario)
    )


def puo_riaprire(user: User, diario: Diario) -> bool:
    """Riapertura (solo staff, regole di scadenza in `Diario.puo_essere_riaperto`)."""
    return _is_staff(user) and diario.puo_essere_riaperto()


def puo_cambiare_csq(user: User, diario: Diario) -> bool:
    """Cambio Capo Squadriglia: staff prima dell'invio; il Capo Reparto del diario in compilazione."""
    if _is_staff(user):
        return diario.stato in STATI_PRIMA_INVIO
    return is_crp_del_diario(user, diario) and diario.stato in STATI_COMPILAZIONE


def puo_cambiare_crp(user: User, diario: Diario) -> bool:
    """Cambio Capo Reparto del singolo diario: solo staff, prima dell'invio."""
    return _is_staff(user) and diario.stato in STATI_PRIMA_INVIO


def puo_cambiare_crp_reparto(user: User) -> bool:
    """Cambio Capo Reparto di tutti i diari non inviati di un reparto: solo staff."""
    return _is_staff(user)


def puo_concedere_dilazione(user: User, diario: Diario) -> bool:
    """Dilazione (gestita dal dominio edizioni): solo staff, prima dell'invio."""
    return _is_staff(user) and diario.stato in STATI_PRIMA_INVIO


def puo_caricare_allegati(user: User, diario: Diario) -> bool:
    """Le foto si caricano con le stesse regole dei moduli 1–5."""
    return puo_modificare_moduli(user, diario)


def puo_eliminare_allegati(user: User, diario: Diario) -> bool:
    """Eliminazione foto: ammessa fino all'invio del diario allo staff."""
    if _is_staff(user):
        return True
    if diario.stato in STATI_COMPILAZIONE:
        return is_csq_del_diario(user, diario)
    if diario.stato == StatoDiario.RELAZIONE_FINALE:
        return is_csq_del_diario(user, diario) or is_crp_del_diario(user, diario)
    return False


def puo_scaricare_pdf(user: User) -> bool:
    """Il PDF (moduli 1–6) non è mai disponibile al Capo Squadriglia."""
    return user.ruolo != Ruolo.CSQ


def pdf_disponibile_nello_stato(diario: Diario) -> bool:
    return diario.stato in STATI_PDF
