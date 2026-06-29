# apps/evaluations/actions.py
"""Funzioni di servizio per le azioni FSM sul Diario e la Valutazione.

Unica fonte di verità per permessi e logica di dominio — usata sia dalle
view web sia dai router API. Le view web mantengono RuoloRequiredMixin
per il controllo HTTP grossolano; queste funzioni aggiungono il controllo
fine-grained (es. "il CSQ deve essere il CSQ di questo specifico diario").
"""
from __future__ import annotations

from apps.accounts.models import Ruolo
from apps.diaries.models import Diario, StatoDiario
from apps.evaluations.models import AssegnazionePGV, EsitoValutazione, StatoValutazione, Valutazione


class AzioneNonConsentita(ValueError):
    """Azione non eseguibile per permessi o stato corrente."""


class PermessoNegato(AzioneNonConsentita):
    """L'utente non ha il ruolo/l'accesso necessario."""


class StatoNonValido(AzioneNonConsentita):
    """Il diario o la valutazione non sono nello stato richiesto."""


# ---------------------------------------------------------------------------
# Transizioni FSM
# ---------------------------------------------------------------------------

def csq_invia(diario: Diario, user) -> None:
    """IN_COMPILAZIONE → RELAZIONE_FINALE (Capo Squadriglia o staff)."""
    is_csq_proprio = (
        user.ruolo == Ruolo.CSQ
        and user.socio is not None
        and diario.csq_id == user.socio.pk
    )
    if not (user.is_superuser or user.is_staff_plancia or is_csq_proprio):
        raise PermessoNegato("Solo il Capo Squadriglia del diario può inviare la propria parte.")
    if diario.stato != StatoDiario.IN_COMPILAZIONE:
        raise StatoNonValido("Il diario deve essere in compilazione.")
    diario.csq_invia()


def invia(diario: Diario, user) -> None:
    """RELAZIONE_FINALE → INVIATO (Capo Reparto o staff)."""
    is_crp_proprio = (
        user.ruolo == Ruolo.CRP
        and user.socio is not None
        and diario.crp_id == user.socio.pk
    )
    if not (user.is_superuser or user.is_staff_plancia or is_crp_proprio):
        raise PermessoNegato("Solo il Capo Reparto del diario può inviare il diario.")
    if diario.stato != StatoDiario.RELAZIONE_FINALE:
        raise StatoNonValido("Il diario deve essere in stato relazione finale.")
    diario.invia()


def riapri(diario: Diario, user) -> None:
    """NON_APPROVATO / MAGGIORI_INFO → IN_COMPILAZIONE (solo staff)."""
    if not (user.is_superuser or user.is_staff_plancia):
        raise PermessoNegato("Solo lo staff può riaprire un diario.")
    if not diario.puo_essere_riaperto():
        raise StatoNonValido("Riapertura non consentita: verifica stato e scadenza.")
    diario.riapri()


# ---------------------------------------------------------------------------
# Azioni Valutazione
# ---------------------------------------------------------------------------

def assegna_pgv(diario: Diario, pgv_user, user) -> tuple[bool, Valutazione]:
    """Assegna un membro PGV a un diario. Ritorna (creata, valutazione)."""
    if not (user.is_superuser or user.is_staff_plancia):
        raise PermessoNegato("Accesso non consentito.")
    if pgv_user.ruolo != Ruolo.PGV:
        raise StatoNonValido("L'utente indicato non è un membro della Pattuglia GV.")
    val, _ = Valutazione.objects.get_or_create(diario=diario)
    _, created = AssegnazionePGV.objects.get_or_create(
        valutazione=val, pgv=pgv_user, defaults={"assegnato_da": user}
    )
    return created, val


def valuta_direttamente(diario: Diario, esito: str, note: str, user) -> Valutazione:
    """Incaricato EG/Admin/Segreteria valuta direttamente (esito definitivo)."""
    if not (user.is_superuser or user.is_staff_plancia):
        raise PermessoNegato("Accesso non consentito.")
    if diario.stato not in (StatoDiario.INVIATO, StatoDiario.IN_VALUTAZIONE, StatoDiario.IN_REVISIONE):
        raise StatoNonValido("Il diario non è in uno stato valutabile.")
    if esito not in EsitoValutazione.values:
        raise StatoNonValido("Esito non valido.")
    if diario.stato == StatoDiario.INVIATO:
        diario.avvia_valutazione()
    val, _ = Valutazione.objects.get_or_create(diario=diario)
    val.valuta_direttamente(user, esito, note)
    return val


def proponi_pgv(diario: Diario, esito: str, note: str, pgv) -> Valutazione:
    """Membro PGV propone Approvata/Non approvata."""
    if pgv.ruolo != Ruolo.PGV:
        raise PermessoNegato("Solo un membro della Pattuglia GV può fare una proposta.")
    val = _get_val(diario)
    if not val.assegnazioni_pgv.filter(pgv=pgv).exists():
        raise PermessoNegato("Non sei assegnato a questo diario.")
    if esito == EsitoValutazione.MAGGIORI_INFO:
        raise StatoNonValido("Maggiori informazioni non può essere proposto dalla Pattuglia GV.")
    if esito not in EsitoValutazione.values:
        raise StatoNonValido("Esito non valido.")
    val.proponi_pgv(pgv, esito, note)
    return val


def conferma_proposta(diario: Diario, note: str, user) -> Valutazione:
    """Incaricato EG/Admin conferma la proposta PGV."""
    if not (user.is_superuser or user.is_staff_plancia):
        raise PermessoNegato("Accesso non consentito.")
    val = _get_val(diario)
    if val.stato != StatoValutazione.IN_REVISIONE:
        raise StatoNonValido("Nessuna proposta in revisione da confermare.")
    val.conferma(user, note)
    return val


def rigetta_proposta(diario: Diario, user) -> Valutazione:
    """Incaricato EG/Admin rigetta la proposta PGV."""
    if not (user.is_superuser or user.is_staff_plancia):
        raise PermessoNegato("Accesso non consentito.")
    val = _get_val(diario)
    if val.stato != StatoValutazione.IN_REVISIONE:
        raise StatoNonValido("Nessuna proposta da rigettare.")
    val.rigetta_proposta(user)
    return val


def modifica_valutazione(diario: Diario, esito: str, note: str, user) -> Valutazione:
    """Incaricato EG/Admin modifica l'esito prima della pubblicazione."""
    if not (user.is_superuser or user.is_staff_plancia):
        raise PermessoNegato("Accesso non consentito.")
    if esito not in EsitoValutazione.values:
        raise StatoNonValido("Esito non valido.")
    val = _get_val(diario)
    if val.pubblicata:
        raise StatoNonValido("Non è possibile modificare un esito già pubblicato.")
    val.modifica(user, esito, note)
    return val


def pubblica_esito(diario: Diario, user) -> None:
    """Pubblica l'esito di un singolo diario."""
    if not (user.is_superuser or user.is_staff_plancia):
        raise PermessoNegato("Accesso non consentito.")
    val = _get_val(diario)
    if not val.esito:
        raise StatoNonValido("Nessun esito da pubblicare.")
    from django.utils import timezone
    diario.pubblicato_at = timezone.now()
    diario.save(update_fields=["pubblicato_at"])


def pubblica_tutti(edizione, user, scadenza: str | None = None) -> int:
    """Pubblica tutti gli esiti confermati di un'edizione. Ritorna il conteggio."""
    if not (user.is_superuser or user.is_staff_plancia):
        raise PermessoNegato("Accesso non consentito.")
    from django.utils import timezone

    qs = edizione.diari.filter(
        pubblicato_at__isnull=True,
        valutazione__stato=StatoValutazione.CONFERMATA,
        valutazione__esito__isnull=False,
    )
    if scadenza:
        qs = qs.filter(scadenza_riferimento=scadenza)

    count = 0
    ts = timezone.now()
    for d in qs.select_related("valutazione"):
        d.pubblicato_at = ts
        d.save(update_fields=["pubblicato_at"])
        count += 1
    return count


def _get_val(diario: Diario) -> Valutazione:
    try:
        return diario.valutazione
    except Valutazione.DoesNotExist:
        raise StatoNonValido("Nessuna valutazione attiva per questo diario.") from None
