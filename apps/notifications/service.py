# apps/notifications/service.py
"""Logica di invio inviti e notifiche email. Vedi docs sez. 8."""
from __future__ import annotations

import logging

from django.conf import settings
from django.urls import reverse

from apps.notifications.models import Invito, StatoInvito, TipoInvito, render_mail

try:
    from anymail.message import AnymailMessage as _MailMessageClass
except ImportError:
    from django.core.mail import EmailMessage as _MailMessageClass  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _titolo_piattaforma() -> str:
    from apps.siteconfig.models import Impostazioni
    return Impostazioni.get().titolo


def _from_email() -> str:
    from apps.siteconfig.models import Impostazioni
    imp = Impostazioni.get()
    return imp.from_email_completo or settings.DEFAULT_FROM_EMAIL


def _link_attivazione(token) -> str:
    path = reverse("notifications:attiva_invito", kwargs={"token": str(token)})
    base = getattr(settings, "BASE_URL", "http://localhost:8000")
    return f"{base}{path}"


def invia_invito(invito: Invito, backend_tipo: str = "standard") -> bool:
    """Invia l'email di invito e aggiorna lo stato.

    Ritorna True se l'invio ha avuto successo.
    """
    utente = invito.utente
    socio = utente.socio
    chiave = f"invito_{invito.ruolo_target}"  # invito_csq / invito_crp / invito_pgv

    contesto: dict = {
        "nome": socio.nome if socio else utente.first_name,
        "cognome": socio.cognome if socio else utente.last_name,
        "titolo_piattaforma": _titolo_piattaforma(),
        "link_attivazione": _link_attivazione(invito.token),
    }

    if invito.diario:
        diario = invito.diario
        contesto["edizione"] = str(diario.edizione)
        contesto["squadriglia"] = diario.squadriglia.nome
        contesto["reparto"] = str(diario.squadriglia.reparto)
        scad = diario.scadenza_effettiva()
        contesto["scadenza"] = scad.strftime("%d/%m/%Y") if scad else ""

    try:
        oggetto, corpo = render_mail(chiave, contesto)
    except Exception:
        oggetto = f"Invito Plancia — {_titolo_piattaforma()}"
        corpo = (
            f"<p>Ciao {contesto.get('nome', '')},</p>"
            f"<p>Clicca il link per accedere: "
            f"<a href=\"{contesto['link_attivazione']}\">{contesto['link_attivazione']}</a></p>"
        )

    # Non inviare se l'email è un placeholder interno
    email_dest = utente.email
    if not email_dest or email_dest.endswith("@noemail.internal"):
        return False

    try:
        from apps.siteconfig.email_backends import get_connection_per_tipo

        msg = _MailMessageClass(
            subject=oggetto,
            body=corpo,
            from_email=_from_email(),
            to=[email_dest],
        )
        msg.content_subtype = "html"
        if hasattr(msg, "metadata"):
            msg.metadata = {"invito_pk": str(invito.pk)}
        msg.connection = get_connection_per_tipo(backend_tipo)
        msg.send()
        return True
    except Exception:
        logger.exception("Errore invio email invito pk=%s a %s", invito.pk, email_dest)
        return False


def crea_e_invia_invito(diario, utente, ruolo_target: str) -> Invito:
    """Crea un Invito e lo invia via email (o lo accoda a Celery)."""
    from apps.notifications.tasks import task_invia_invito

    invito = Invito.objects.create(
        diario=diario, utente=utente, ruolo_target=ruolo_target
    )
    task_invia_invito.delay(invito.pk)
    return invito


def reinvia_invito(invito: Invito) -> Invito:
    """Crea un nuovo Invito invalidando il precedente e lo invia."""
    invito.stato = StatoInvito.SCADUTO
    invito.save(update_fields=["stato"])
    return crea_e_invia_invito(invito.diario, invito.utente, invito.ruolo_target)


# ---------------------------------------------------------------------------
# Gestione utenti per inviti
# ---------------------------------------------------------------------------

def _email_placeholder(codice_socio: str) -> str:
    return f"noemail.{codice_socio}@noemail.internal"


def crea_o_ottieni_utente_per_socio(socio, ruolo: str):
    """Restituisce l'User collegato al Socio, creandolo se non esiste.

    Per i CSQ senza email usa un placeholder interno. La password è inutilizzabile
    finché l'utente non si attiva via token o codice socio.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if hasattr(socio, "utente") and socio.utente is not None:
        return socio.utente

    email = socio.email if socio.email else _email_placeholder(socio.codice_socio)

    # Se esiste già un User con questa email (es. da un import precedente) riusalo
    try:
        utente = User.objects.get(email=email)
        if utente.socio is None:
            utente.socio = socio
            utente.save(update_fields=["socio"])
        return utente
    except User.DoesNotExist:
        pass

    utente = User(
        email=email,
        username=socio.codice_socio,
        first_name=socio.nome,
        last_name=socio.cognome,
        ruolo=ruolo,
        socio=socio,
        is_active=True,
    )
    utente.set_unusable_password()
    utente.save()
    return utente


# ---------------------------------------------------------------------------
# Inviti per edizione
# ---------------------------------------------------------------------------

def _invalida_inviti_precedenti(utente, ruolo_target: str) -> None:
    Invito.objects.filter(
        utente=utente,
        ruolo_target=ruolo_target,
        stato=StatoInvito.INVIATO,
    ).update(stato=StatoInvito.SCADUTO)


def invia_inviti_capi_per_edizione(edizione, backend_tipo: str = "massivo") -> dict:
    """Crea e invia inviti a tutti i Capi Reparto dell'edizione che non hanno ancora un invito attivo.

    Restituisce contatori {inviati, saltati_gia_attivati, saltati_senza_email}.
    """
    from apps.diaries.models import Diario
    from apps.notifications.tasks import task_invia_invito

    inviati = saltati_gia_attivati = saltati_senza_email = 0

    diari = (
        Diario.objects
        .filter(edizione=edizione)
        .select_related("crp", "squadriglia__reparto")
        .exclude(crp__isnull=True)
    )

    seen_crp = set()
    for diario in diari:
        crp = diario.crp
        if crp.pk in seen_crp:
            continue
        seen_crp.add(crp.pk)

        if not crp.email or crp.email.endswith("@noemail.internal"):
            saltati_senza_email += 1
            continue

        utente = crea_o_ottieni_utente_per_socio(crp, "crp")

        # Salta se ha già un invito attivato
        if Invito.objects.filter(utente=utente, ruolo_target="crp",
                                 stato=StatoInvito.ATTIVATO).exists():
            saltati_gia_attivati += 1
            continue

        _invalida_inviti_precedenti(utente, "crp")
        invito = Invito.objects.create(
            diario=diario, utente=utente, ruolo_target="crp",
            tipo=TipoInvito.STANDARD,
        )
        task_invia_invito.delay(invito.pk, backend_tipo=backend_tipo)
        inviati += 1

    return {
        "inviati": inviati,
        "saltati_gia_attivati": saltati_gia_attivati,
        "saltati_senza_email": saltati_senza_email,
    }


def invia_inviti_csq_per_edizione(edizione, backend_tipo: str = "massivo") -> dict:
    """Crea inviti per tutti i Capi Squadriglia dell'edizione.

    Per ciascun Capo Reparto invia una email riepilogativa con la lista dei suoi
    Capi Squadriglia e i rispettivi link di attivazione.
    Come canale secondario, invia l'invito direttamente al CSQ se ha un'email valida.
    Restituisce contatori {inviti_csq_creati, email_crp_inviate, email_csq_inviate}.
    """
    from apps.diaries.models import Diario
    from apps.notifications.tasks import task_invia_invito

    inviti_csq_creati = email_crp_inviate = email_csq_inviate = 0

    diari = (
        Diario.objects
        .filter(edizione=edizione)
        .select_related("csq", "crp", "squadriglia__reparto")
        .exclude(csq__isnull=True)
    )

    # Raggruppa per CRP per la email riepilogativa
    by_crp: dict = {}
    for diario in diari:
        csq = diario.csq
        utente_csq = crea_o_ottieni_utente_per_socio(csq, "csq")

        if Invito.objects.filter(utente=utente_csq, ruolo_target="csq",
                                 stato=StatoInvito.ATTIVATO).exists():
            continue

        _invalida_inviti_precedenti(utente_csq, "csq")
        invito = Invito.objects.create(
            diario=diario, utente=utente_csq, ruolo_target="csq",
            tipo=TipoInvito.CODICE_SOCIO,
        )
        inviti_csq_creati += 1

        # Canale secondario: email diretta al CSQ
        if csq.email and not csq.email.endswith("@noemail.internal"):
            task_invia_invito.delay(invito.pk, backend_tipo=backend_tipo)
            email_csq_inviate += 1

        # Accumula per email riepilogativa al CRP
        crp = diario.crp
        if crp and crp.email and not crp.email.endswith("@noemail.internal"):
            crp_key = crp.pk
            if crp_key not in by_crp:
                by_crp[crp_key] = {"crp": crp, "diario_ref": diario, "squadriglie": []}
            by_crp[crp_key]["squadriglie"].append({
                "nome_csq": f"{csq.nome} {csq.cognome}",
                "squadriglia": diario.squadriglia.nome,
                "link_attivazione": _link_attivazione(invito.token),
            })

    # Invia una email riepilogativa per ogni CRP
    for entry in by_crp.values():
        ok = _invia_riepilogo_csq_a_crp(
            crp=entry["crp"],
            diario_ref=entry["diario_ref"],
            squadriglie=entry["squadriglie"],
            backend_tipo=backend_tipo,
        )
        if ok:
            email_crp_inviate += 1

    return {
        "inviti_csq_creati": inviti_csq_creati,
        "email_crp_inviate": email_crp_inviate,
        "email_csq_inviate": email_csq_inviate,
    }


def _invia_riepilogo_csq_a_crp(crp, diario_ref, squadriglie: list, backend_tipo: str = "massivo") -> bool:
    """Invia al CRP la email con la tabella dei suoi CSQ e i link di attivazione."""
    from django.template.loader import render_to_string

    titolo = _titolo_piattaforma()
    corpo = render_to_string("mail/invito_crp_csq_lista.html", {
        "nome": crp.nome,
        "cognome": crp.cognome,
        "titolo_piattaforma": titolo,
        "edizione": str(diario_ref.edizione),
        "reparto": str(diario_ref.squadriglia.reparto),
        "squadriglie_lista": squadriglie,
    })

    try:
        from apps.siteconfig.email_backends import get_connection_per_tipo

        msg = _MailMessageClass(
            subject=f"{titolo} — Attivazione account Capi Squadriglia",
            body=corpo,
            from_email=_from_email(),
            to=[crp.email],
        )
        msg.content_subtype = "html"
        msg.connection = get_connection_per_tipo(backend_tipo)
        msg.send()
        return True
    except Exception:
        logger.exception("Errore invio email riepilogo CSQ a CRP %s", crp.email)
        return False
