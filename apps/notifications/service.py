# apps/notifications/service.py
"""Logica di invio inviti e notifiche email. Vedi docs sez. 8."""
from __future__ import annotations

import logging

from django.conf import settings

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
    # Pagina della SPA (frontend/src/views/auth/AttivazioneInvitoView.vue)
    base = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/invito/{token}"


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
        msg = _MailMessageClass(
            subject=oggetto,
            body=corpo,
            from_email=_from_email(),
            to=[email_dest],
        )
        msg.content_subtype = "html"
        if hasattr(msg, "metadata"):
            msg.metadata = {"invito_pk": str(invito.pk)}
        msg.send(using=backend_tipo)
        return True
    except Exception:
        logger.exception("Errore invio email invito pk=%s a %s", invito.pk, email_dest)
        return False


def crea_e_invia_invito(diario, utente, ruolo_target: str, tipo: str | None = None) -> Invito:
    """Crea un Invito e lo invia via email (o lo accoda a Celery).

    Gli inviti ai Capi Squadriglia sono sempre di tipo CODICE_SOCIO (l'attivazione
    richiede la conferma del codice socio), salvo `tipo` esplicito.
    """
    from apps.notifications.tasks import task_invia_invito

    if tipo is None:
        tipo = TipoInvito.CODICE_SOCIO if ruolo_target == "csq" else TipoInvito.STANDARD
    invito = Invito.objects.create(
        diario=diario, utente=utente, ruolo_target=ruolo_target, tipo=tipo
    )
    task_invia_invito.delay(invito.pk)
    return invito


def reinvia_invito(invito: Invito) -> Invito:
    """Crea un nuovo Invito (stesso tipo) invalidando il precedente e lo invia."""
    invito.stato = StatoInvito.SCADUTO
    invito.save(update_fields=["stato"])
    return crea_e_invia_invito(
        invito.diario, invito.utente, invito.ruolo_target, tipo=invito.tipo
    )


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
        assert crp is not None  # esclusi dal queryset
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
        assert csq is not None  # esclusi dal queryset
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
        msg = _MailMessageClass(
            subject=f"{titolo} — Attivazione account Capi Squadriglia",
            body=corpo,
            from_email=_from_email(),
            to=[crp.email],
        )
        msg.content_subtype = "html"
        msg.send(using=backend_tipo)
        return True
    except Exception:
        logger.exception("Errore invio email riepilogo CSQ a CRP %s", crp.email)
        return False


# ---------------------------------------------------------------------------
# Gestione inviti — logica usata dall'API
# ---------------------------------------------------------------------------

BACKEND_INVIO = ("standard", "massivo")
TIPI_INVIO_EDIZIONE = ("capi", "csq")
RUOLI_INVITO_DIARIO = ("csq", "crp")


def edizione_inviti_attiva():
    """Edizione su cui si lavorano gli inviti: la più recente aperta o in valutazione."""
    from apps.editions.models import Edizione, StatoEdizione

    return (
        Edizione.objects.filter(stato__in=[StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE])
        .order_by("-anno")
        .first()
    )


def _chiave_invio(invito):
    from django.utils import timezone

    return invito.inviato_at or timezone.datetime.min.replace(tzinfo=timezone.UTC)


def diari_con_ultimi_inviti(edizione) -> list:
    """Diari dell'edizione con `ultimo_invito_csq` e `ultimo_invito_crp` valorizzati.

    Un Capo Reparto con N squadriglie ha l'invito su un solo diario: gli altri diari
    ereditano il suo invito più recente, così lo stato mostrato è corretto ovunque.
    """
    from apps.accounts.models import Ruolo
    from apps.diaries.models import Diario

    diari = list(
        Diario.objects.filter(edizione=edizione)
        .select_related("csq__utente", "crp__utente", "squadriglia__reparto__gruppo__zona")
        .prefetch_related("inviti")
        .order_by("squadriglia__reparto__nome", "squadriglia__nome")
    )
    invito_per_crp: dict[int, Invito] = {}
    for d in diari:
        if not d.crp:
            continue
        for inv in d.inviti.all():
            if inv.ruolo_target == Ruolo.CRP:
                attuale = invito_per_crp.get(d.crp.pk)
                if attuale is None or _chiave_invio(inv) > _chiave_invio(attuale):
                    invito_per_crp[d.crp.pk] = inv
    for d in diari:
        inviti = sorted(d.inviti.all(), key=_chiave_invio, reverse=True)
        d.ultimo_invito_csq = next(  # type: ignore[attr-defined]  # attributo calcolato
            (i for i in inviti if i.ruolo_target == Ruolo.CSQ), None
        )
        d.ultimo_invito_crp = (  # type: ignore[attr-defined]  # attributo calcolato
            invito_per_crp.get(d.crp.pk) if d.crp else None
        )
    return diari


def diari_inviti_crp(edizione, socio) -> list:
    """Diari del Capo Reparto `socio` con l'ultimo invito al rispettivo Capo Squadriglia."""
    from apps.accounts.models import Ruolo
    from apps.diaries.models import Diario

    if not edizione or not socio:
        return []
    diari = list(
        Diario.objects.filter(edizione=edizione, crp=socio)
        .select_related("csq__utente", "squadriglia__reparto")
        .prefetch_related("inviti")
        .order_by("squadriglia__nome")
    )
    for d in diari:
        inviti = sorted(d.inviti.all(), key=_chiave_invio, reverse=True)
        d.ultimo_invito_csq = next(  # type: ignore[attr-defined]  # attributo calcolato
            (i for i in inviti if i.ruolo_target == Ruolo.CSQ), None
        )
    return diari


def calcola_stato_inviti(diari) -> dict:
    """Contatori aggregati degli inviti di un'edizione.

    I Capi Reparto sono deduplicati: chi gestisce N squadriglie conta una volta sola.
    """
    csq_totale = csq_inviati = csq_attivati = 0
    crp_inviti: dict[int, list] = {}

    for diario in diari:
        inviti_diario = list(diario.inviti.all())
        csq_totale += 1
        inv_csq = [i for i in inviti_diario if i.ruolo_target == "csq"]
        if any(i.stato == StatoInvito.ATTIVATO for i in inv_csq):
            csq_attivati += 1
        elif any(i.stato == StatoInvito.INVIATO for i in inv_csq):
            csq_inviati += 1
        if diario.crp:
            crp_inviti.setdefault(diario.crp.pk, []).extend(
                i for i in inviti_diario if i.ruolo_target == "crp"
            )

    capi_totale = len(crp_inviti)
    capi_attivati = capi_inviati = 0
    for inviti in crp_inviti.values():
        if any(i.stato == StatoInvito.ATTIVATO for i in inviti):
            capi_attivati += 1
        elif any(i.stato == StatoInvito.INVIATO for i in inviti):
            capi_inviati += 1

    return {
        "capi_totale": capi_totale,
        "capi_inviati": capi_inviati,
        "capi_attivati": capi_attivati,
        "capi_da_invitare": capi_totale - capi_inviati - capi_attivati,
        "csq_totale": csq_totale,
        "csq_inviati": csq_inviati,
        "csq_attivati": csq_attivati,
        "csq_da_invitare": csq_totale - csq_inviati - csq_attivati,
    }


def avvia_invio_inviti_edizione(edizione, tipo: str, backend_tipo: str = "massivo") -> str:
    """Accoda l'invio massivo degli inviti dell'edizione; restituisce il messaggio per l'utente.

    `tipo`: "capi" (Capi Reparto) o "csq" (Capi Squadriglia, link consegnati ai Capi Reparto).
    `backend_tipo`: mailer "standard" o "massivo" (alias di settings.MAILERS).
    """
    from django.core.exceptions import ValidationError

    from apps.notifications.tasks import (
        task_invia_inviti_capi_edizione,
        task_invia_inviti_csq_edizione,
    )

    if edizione is None:
        raise ValidationError("Nessuna edizione attiva trovata.")
    if backend_tipo not in BACKEND_INVIO:
        raise ValidationError(
            {"backend": ["Canale di invio non valido: usa «standard» o «massivo»."]}
        )
    if tipo == "capi":
        task_invia_inviti_capi_edizione.delay(edizione.pk, backend_tipo=backend_tipo)
        return "Invio inviti ai Capi Reparto accodato. Riceveranno l'email entro pochi minuti."
    if tipo == "csq":
        task_invia_inviti_csq_edizione.delay(edizione.pk, backend_tipo=backend_tipo)
        return (
            "Invio inviti ai Capi Squadriglia accodato. "
            "I Capi Reparto riceveranno la lista dei loro Capi Squadriglia "
            "con i rispettivi link di accesso."
        )
    raise ValidationError({"tipo": ["Tipo di invito non riconosciuto."]})


def accoda_inviti_diario(diario, ruoli: list[str] | None = None) -> list[str]:
    """Accoda l'invio degli inviti mancanti di un diario (Capo Squadriglia e/o Capo Reparto)."""
    from django.core.exceptions import ValidationError

    from apps.notifications.tasks import task_invia_inviti_bulk

    ruoli = list(ruoli or RUOLI_INVITO_DIARIO)
    non_validi = [r for r in ruoli if r not in RUOLI_INVITO_DIARIO]
    if non_validi:
        raise ValidationError({"ruoli": [f"Ruolo non valido: {', '.join(non_validi)}."]})
    task_invia_inviti_bulk.delay(diario.pk, ruoli)
    return ruoli


def verifica_reinvio(user, invito: Invito) -> None:
    """Chi può reinviare: staff, oppure il Capo Reparto per gli inviti ai Capi Squadriglia
    dei propri diari. Un invito già attivato non si reinvia.
    """
    from django.core.exceptions import PermissionDenied, ValidationError

    from apps.accounts.models import Ruolo

    staff = user.is_superuser or user.ruolo in (
        Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG,
    )
    if not staff and (
        user.ruolo != Ruolo.CRP
        or not user.socio_id
        or not invito.diario
        or invito.ruolo_target != Ruolo.CSQ
        or invito.diario.crp_id != user.socio_id
    ):
        raise PermissionDenied("Non sei autorizzato a reinviare questo invito.")
    if invito.stato == StatoInvito.ATTIVATO:
        raise ValidationError("Questo invito è già stato attivato.")


# ---------------------------------------------------------------------------
# Attivazione account da invito
# ---------------------------------------------------------------------------

def controlla_invito_attivabile(invito: Invito) -> None:
    """ValidationError se l'invito è già stato usato o è scaduto."""
    from django.core.exceptions import ValidationError

    if invito.stato == StatoInvito.ATTIVATO:
        raise ValidationError("Questo invito è già stato attivato.", code="attivato")
    if invito.stato == StatoInvito.SCADUTO:
        raise ValidationError(
            "Questo invito è scaduto. Contatta la segreteria per un nuovo invito.",
            code="scaduto",
        )


def conferma_codice_socio(invito: Invito, codice: str, email: str) -> None:
    """Verifica codice socio ed email di un invito Capo Squadriglia e aggiorna l'email.

    Solleva ValidationError con l'errore sul campo (`codice_socio` o `email`).
    """
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    codice = (codice or "").strip()
    email = (email or "").strip().lower()
    utente = invito.utente
    socio = utente.socio

    if not socio or codice != socio.codice_socio:
        raise ValidationError({"codice_socio": [
            "Codice socio non corretto. Controlla il codice sulla tua tessera AGESCI."
        ]})
    if not email:
        raise ValidationError({"email": ["Inserisci il tuo indirizzo email."]})
    try:
        validate_email(email)
    except ValidationError:
        raise ValidationError({"email": ["L'indirizzo email non è valido."]}) from None

    if utente.email.endswith("@noemail.internal") or utente.email != email:
        User = get_user_model()
        if User.objects.filter(email=email).exclude(pk=utente.pk).exists():
            raise ValidationError({"email": [
                "Questa email è già registrata. Se hai già un account contatta la segreteria."
            ]})
        utente.email = email
        utente.save(update_fields=["email"])
        if socio.email != email:
            socio.email = email
            socio.save(update_fields=["email"])


def login_da_invito_consentito(utente) -> bool:
    """Il link dell'invito può aprire la sessione solo per account senza credenziali proprie.

    Chi ha già una password o un ruolo di staff (MFA obbligatoria) deve accedere normalmente:
    altrimenti il link email aggirerebbe password e MFA.
    """
    from apps.accounts.models import Ruolo

    if utente.is_superuser or utente.has_usable_password():
        return False
    ruoli = set(utente.ruoli_attivi) | {utente.ruolo}
    return not ruoli & {Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG}


def completa_attivazione_invito(invito: Invito):
    """Segna l'invito come attivato e garantisce la Nomina per il ruolo dell'invito.

    Restituisce l'utente da autenticare (il login resta a carico del chiamante).
    """
    from apps.accounts.models import Nomina

    invito.attiva()
    utente = invito.utente
    # Serve quando l'utente esisteva già con un ruolo diverso (es. Admin che è anche
    # Capo Reparto): questo è l'unico punto di attivazione.
    edizione = invito.diario.edizione if invito.diario else None
    if not Nomina.objects.filter(utente=utente, ruolo=invito.ruolo_target, attiva=True).exists():
        aveva_ruoli = Nomina.objects.filter(utente=utente, attiva=True).exists()
        Nomina.objects.create(
            utente=utente,
            socio=getattr(utente, "socio", None),
            ruolo=invito.ruolo_target,
            nominato_da=None,
            edizione=edizione,
            attiva=True,
        )
        if not aveva_ruoli:
            utente.ruolo = invito.ruolo_target
            utente.save(update_fields=["ruolo"])
    return utente
