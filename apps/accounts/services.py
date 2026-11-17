"""Servizi di dominio per utenti, profilo, ruoli e sessioni.

Usati dall'API (`apps/api/routers/me.py`, `apps/api/routers/utenti.py`): le regole stanno
qui, non nei router. Le regole di nomina
restano in `apps.accounts.roles`.

Eccezioni: `PermissionDenied` (permesso negato), `ValidationError` (dati non validi, anche
per campo), `ValueError`/`PermissionError` da `roles.nomina` (lasciate passare: le viste le
l'API le traduce in 422/403).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, QuerySet

from apps.accounts.models import Ruolo, User
from apps.accounts.roles import ROLE_CREATABLE_BY, ROLE_REQUIRES_CATEGORY, nomina, puo_nominare

if TYPE_CHECKING:
    from django.http import HttpRequest

    from apps.accounts.models import Nomina


# ---------------------------------------------------------------------------
# Ruoli nominabili / creabili
# ---------------------------------------------------------------------------

# Ruoli creabili con il flusso "utente staff" (senza Socio) e chi può crearli.
RUOLI_STAFF: dict[str, set[str]] = {
    Ruolo.ADMIN: {Ruolo.ADMIN},
    Ruolo.SEGRETERIA: {Ruolo.ADMIN},
    Ruolo.INCARICATO_EG: {Ruolo.ADMIN, Ruolo.SEGRETERIA},
}


def ruoli_nominabili(attore: User, solo_capi: bool = False) -> list[tuple[str, str]]:
    """Ruoli (chiave, etichetta) che `attore` può assegnare.

    `solo_capi=True` esclude i ruoli riservati ai ragazzi (Capo Squadriglia): è il caso della
    creazione di un account da un Socio capo.
    """
    return [
        (r, label)
        for r, label in Ruolo.choices
        if (attore.ruolo in ROLE_CREATABLE_BY.get(r, set()) or attore.is_superuser)
        and not (solo_capi and ROLE_REQUIRES_CATEGORY.get(r) == "ragazzo")
    ]


def ruoli_staff_creabili(attore: User) -> list[tuple[str, str]]:
    """Ruoli (chiave, etichetta) creabili da `attore` col flusso utente staff senza Socio."""
    return [
        (r, Ruolo(r).label)
        for r, creatori in RUOLI_STAFF.items()
        if attore.ruolo in creatori or attore.is_superuser
    ]


# ---------------------------------------------------------------------------
# Lista utenti
# ---------------------------------------------------------------------------


def utenti_filtrati(ruolo: str | None = None, q: str | None = None) -> QuerySet[User]:
    """Utenti per la pagina Utenti: filtro per ruolo attivo e ricerca su email/nome/cognome."""
    qs = User.objects.select_related("socio", "socio__gruppo", "socio__zona").order_by(
        "ruolo", "email"
    )
    if ruolo in Ruolo.values:
        qs = qs.filter(ruolo=ruolo)
    q = (q or "").strip()
    if q:
        qs = qs.filter(
            Q(email__icontains=q) | Q(socio__cognome__icontains=q) | Q(socio__nome__icontains=q)
        )
    return qs


# ---------------------------------------------------------------------------
# Profilo
# ---------------------------------------------------------------------------


def puo_modificare_email(user: User) -> bool:
    """Solo il Capo Squadriglia (ragazzo) può cambiare da sé la propria email."""
    return bool(
        user.ruolo == Ruolo.CSQ and user.socio and user.socio.email_modificabile_dall_interessato
    )


def puo_modificare_nome(user: User) -> bool:
    """Nome e cognome si modificano da sé solo senza Socio: altrimenti vengono dall'anagrafica."""
    return user.socio is None


def aggiorna_nome(user: User, first_name: str, last_name: str, attore: User | None = None) -> None:
    """Aggiorna nome e cognome di un utente senza Socio (es. arrivato da Sestante): da sé, o da
    Admin/Segreteria (`attore`, regole in `roles.puo_modificare_nome_di`)."""
    from apps.accounts.roles import puo_modificare_nome_di

    if not puo_modificare_nome(user):
        raise PermissionDenied("Nome e cognome vengono dall'anagrafica del socio.")
    if attore is not None and attore.pk != user.pk and not puo_modificare_nome_di(attore, user):
        raise PermissionDenied("Non puoi modificare il nome di questo utente.")
    first_name, last_name = (first_name or "").strip(), (last_name or "").strip()
    if not first_name:
        raise ValidationError({"first_name": "Il nome non può essere vuoto."})
    errori = {}
    for campo, valore in (("first_name", first_name), ("last_name", last_name)):
        massimo = getattr(User._meta.get_field(campo), "max_length", None)
        if massimo and len(valore) > massimo:
            errori[campo] = f"Al massimo {massimo} caratteri."
    if errori:
        raise ValidationError(errori)
    user.first_name, user.last_name = first_name, last_name
    user.save(update_fields=["first_name", "last_name"])


def aggiorna_email(user: User, email: str) -> None:
    """Aggiorna l'email dell'utente e del Socio collegato (solo Capo Squadriglia)."""
    if not (user.ruolo == Ruolo.CSQ and user.socio):
        raise PermissionDenied("Solo il Capo Squadriglia può modificare la propria email.")
    email = (email or "").strip()
    if not email:
        raise ValidationError({"email": "L'indirizzo email non può essere vuoto."})
    from django.core.validators import validate_email

    try:
        validate_email(email)
    except ValidationError:
        raise ValidationError({"email": "Indirizzo email non valido."}) from None
    if User.objects.exclude(pk=user.pk).filter(email__iexact=email).exists():
        raise ValidationError({"email": "Questo indirizzo email è già in uso."})
    user.email = email
    user.socio.email = email
    user.socio.save(update_fields=["email"])
    user.save(update_fields=["email"])


def cambia_ruolo_attivo(user: User, ruolo: str) -> bool:
    """Imposta il ruolo attivo se è tra i ruoli attivi non scaduti. True se è cambiato."""
    if ruolo not in user.ruoli_attivi:
        raise ValidationError({"ruolo": "Non hai questo ruolo attivo."})
    if ruolo == user.ruolo:
        return False
    user.ruolo = ruolo
    user.save(update_fields=["ruolo"])
    return True


def termina_altre_sessioni(user: User, session_key_corrente: str | None) -> int:
    """Termina tutte le sessioni dell'utente tranne quella corrente; restituisce quante.

    `UserSession.end()` cancella anche la sessione Django (un semplice delete lascerebbe
    l'utente autenticato nel browser remoto).
    """
    from allauth.usersessions.models import UserSession

    sessioni = list(UserSession.objects.filter(user=user).exclude(session_key=session_key_corrente))
    for s in sessioni:
        s.end()
    return len(sessioni)


# ---------------------------------------------------------------------------
# Creazione utenti e nomine
# ---------------------------------------------------------------------------


def crea_utente_da_socio(attore: User, socio_pk: Any, ruolo: str) -> tuple[User, Nomina]:
    """Crea (o riusa) l'account di un Socio capo e lo nomina a `ruolo`."""
    from apps.org.models import Categoria, Socio

    if ruolo not in Ruolo.values:
        raise ValidationError({"ruolo": "Ruolo non valido."})
    if ruolo not in {r for r, _ in ruoli_nominabili(attore)}:
        raise PermissionDenied(f"Non sei autorizzato ad assegnare il ruolo {Ruolo(ruolo).label}.")
    try:
        socio = Socio.objects.get(pk=socio_pk, categoria=Categoria.CAPO)
    except (Socio.DoesNotExist, ValueError, TypeError):
        raise ValidationError({"socio_id": "Socio (capo) non trovato."}) from None

    from apps.notifications.service import crea_o_ottieni_utente_per_socio

    utente = crea_o_ottieni_utente_per_socio(socio, ruolo)
    return utente, nomina(attore, utente, ruolo)


def crea_utente_staff(
    attore: User,
    email: str,
    first_name: str,
    last_name: str,
    ruolo: str,
    request: HttpRequest | None = None,
) -> tuple[User, Nomina, bool, bool]:
    """Crea un utente Admin/Segreteria/Incaricato EG senza Socio e invia il link per la password.

    Restituisce (utente, nomina, creato, email_inviata). L'invio della mail non blocca la
    creazione: un errore viene registrato nel log e segnalato con `email_inviata=False`.
    """
    if ruolo not in dict(ruoli_staff_creabili(attore)):
        raise ValidationError({"ruolo": "Ruolo non consentito."})
    email = (email or "").strip().lower()
    if not email:
        raise ValidationError({"email": "L'indirizzo email è obbligatorio."})

    from apps.accounts.roles import nomina_staff_diretto

    utente, nomina_obj, creato = nomina_staff_diretto(attore, email, first_name, last_name, ruolo)
    email_inviata = invia_link_password(utente, request)
    return utente, nomina_obj, creato, email_inviata


def invia_link_password(utente: User, request: HttpRequest | None = None) -> bool:
    """Invia l'email di allauth per impostare/reimpostare la password.

    Il link punta alla SPA (`HEADLESS_FRONTEND_URLS["account_reset_password_from_key"]`,
    `/password/reset/{key}`). L'indirizzo è registrato come verificato: chi apre il link ne
    ha dimostrato il possesso, e senza password utilizzabile non si entra altrimenti.
    Restituisce False (e registra l'errore) se l'invio non riesce.
    """
    import logging

    from allauth.account.internal.flows.password_reset import request_password_reset
    from allauth.account.models import EmailAddress
    from allauth.core import context

    try:
        EmailAddress.objects.update_or_create(
            user=utente, email__iexact=utente.email,
            defaults={"email": utente.email, "verified": True, "primary": True},
        )
        with context.request_context(request):
            request_password_reset(request, utente.email, [utente], None)
    except Exception:
        logging.getLogger(__name__).exception(
            "Invio dell'email per impostare la password non riuscito (utente %s)", utente.pk
        )
        return False
    return True


def revoca_nomina(attore: User, nomina_obj: Nomina) -> Nomina:
    """Revoca (attiva=False, il record resta per l'audit) una nomina.

    Regole: stesso permesso della nomina (`ROLE_CREATABLE_BY`); le nomine derivate da Sestante
    si gestiscono solo dal login SSO; non si revocano le proprie nomine. Se il ruolo revocato
    era quello attivo dell'utente, passa al ruolo attivo di rango più alto rimasto.
    """
    from apps.accounts.roles import ROLE_RANK

    if not puo_nominare(attore.ruolo, nomina_obj.ruolo):
        raise PermissionDenied(
            f"Non sei autorizzato a revocare il ruolo {Ruolo(nomina_obj.ruolo).label}."
        )
    if nomina_obj.utente_id == attore.pk:
        raise ValidationError({"__all__": "Non puoi revocare una tua nomina."})
    if nomina_obj.da_sso:
        raise ValidationError(
            {"__all__": "Questa nomina deriva da Sestante: si aggiorna solo al login SSO."}
        )
    if not nomina_obj.attiva:
        raise ValidationError({"__all__": "La nomina è già revocata."})
    nomina_obj.attiva = False
    nomina_obj.save(update_fields=["attiva"])

    utente = nomina_obj.utente
    if utente is not None:
        disponibili = set(utente.ruoli_attivi) | ({Ruolo.ADMIN} if utente.is_superuser else set())
        if utente.ruolo not in disponibili and disponibili:
            utente.ruolo = max(disponibili, key=lambda r: ROLE_RANK.get(r, 0))
            utente.save(update_fields=["ruolo"])
    return nomina_obj


# ---------------------------------------------------------------------------
# Impersonazione (django-hijack)
# ---------------------------------------------------------------------------


def avvia_impersonazione(request: HttpRequest, target: User) -> None:
    """Impersona `target` come farebbe `hijack.views.AcquireUserView`.

    Stesso controllo (`HIJACK_PERMISSION_CHECK` → `roles.can_hijack`), stessa sessione
    (`hijack_history`, durata invariata, niente `last_login`) e stesso segnale `hijack_started`.
    """
    from django.contrib.auth import get_user_model, login
    from django.db import transaction
    from django.db.utils import ConnectionRouter
    from django.utils.module_loading import import_string
    from hijack import signals
    from hijack.conf import settings as hijack_settings
    from hijack.views import get_used_backend, keep_session_age

    hijacker = request.user
    assert isinstance(hijacker, User)  # vista autenticata
    controllo = import_string(hijack_settings.HIJACK_PERMISSION_CHECK)
    if not controllo(hijacker=hijacker, hijacked=target):
        raise PermissionDenied("Non puoi impersonare questo utente.")

    modello = get_user_model()
    with transaction.atomic(using=ConnectionRouter().db_for_write(modello)):
        modello._base_manager.select_for_update().get(pk=hijacker.pk)
        storia = request.session.get("hijack_history", [])
        storia.append(hijacker._meta.pk.value_to_string(hijacker))
        backend = get_used_backend(request)
        backend = f"{backend.__module__}.{backend.__class__.__name__}"
        with signals.no_update_last_login(), keep_session_age(request.session):
            login(request, target, backend=backend)
        request.session["hijack_history"] = storia
        signals.hijack_started.send(
            sender=None, request=request, hijacker=hijacker, hijacked=target
        )


def termina_impersonazione(request: HttpRequest) -> User:
    """Torna all'utente reale come `hijack.views.ReleaseUserView`; restituisce l'operatore."""
    from django.contrib.auth import get_user_model, login
    from django.db import transaction
    from django.db.utils import ConnectionRouter
    from hijack import signals
    from hijack.views import get_used_backend, keep_session_age

    storia = request.session.get("hijack_history", [])
    if not storia:
        raise ValidationError({"__all__": "Nessuna impersonazione in corso."})
    modello = get_user_model()
    hijacked = request.user
    assert isinstance(hijacked, User)  # vista autenticata
    with transaction.atomic(using=ConnectionRouter().db_for_write(modello)):
        modello._base_manager.select_for_update().get(pk=hijacked.pk)
        hijacker = modello.objects.get(pk=storia.pop())
        backend = get_used_backend(request)
        backend = f"{backend.__module__}.{backend.__class__.__name__}"
        with signals.no_update_last_login(), keep_session_age(request.session):
            login(request, hijacker, backend=backend)
        request.session["hijack_history"] = storia
        signals.hijack_ended.send(
            sender=None, request=request, hijacker=hijacker, hijacked=hijacked
        )
    return hijacker


def flag_menu(user: User) -> dict[str, bool]:
    """Voci di menu visibili nella SPA (`me.menu`).

    Servono solo all'interfaccia: ogni endpoint ricontrolla i permessi.
    """
    staff = user.is_staff_plancia or user.is_superuser
    admin = user.ruolo == Ruolo.ADMIN or user.is_superuser
    return {
        "puo_vedere_diari": staff or user.ruolo in (Ruolo.CSQ, Ruolo.CRP, Ruolo.PGV),
        "puo_gestire_edizioni": staff,
        "puo_vedere_utenti": staff,
        "puo_gestire_inviti": staff,
        "puo_gestire_inviti_crp": user.ruolo == Ruolo.CRP,
        "puo_importare": staff,
        "puo_vedere_statistiche": admin or user.ruolo == Ruolo.INCARICATO_EG,
        "puo_vedere_impostazioni": admin,
        "puo_vedere_helpdesk": True,
        "puo_gestire_helpdesk": staff,
        "puo_usare_admin_django": admin,
    }


def impersonato_da(request: HttpRequest) -> User | None:
    """L'operatore reale se la sessione è un'impersonazione in corso, altrimenti None."""
    session = getattr(request, "session", None)
    storia = session.get("hijack_history", []) if session is not None else []
    if not storia:
        return None
    return User.objects.filter(pk=storia[-1]).first()
