# apps/notifications/service.py
"""Logica di invio inviti e notifiche email. Vedi docs sez. 8."""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse

from apps.notifications.models import Invito, StatoInvito, render_mail


def _titolo_piattaforma() -> str:
    from apps.siteconfig.models import Impostazioni
    return Impostazioni.get().titolo


def _link_attivazione(token) -> str:
    path = reverse("notifications:attiva_invito", kwargs={"token": str(token)})
    base = getattr(settings, "BASE_URL", "http://localhost:8000")
    return f"{base}{path}"


def invia_invito(invito: Invito) -> bool:
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
        # Fallback: oggetto e corpo minimi
        oggetto = f"Invito Plancia — {_titolo_piattaforma()}"
        corpo = (
            f"<p>Ciao {contesto.get('nome', '')},</p>"
            f"<p>Clicca il link per accedere: "
            f"<a href=\"{contesto['link_attivazione']}\">{contesto['link_attivazione']}</a></p>"
        )

    try:
        msg = EmailMessage(
            subject=oggetto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[utente.email],
        )
        msg.content_subtype = "html"
        msg.send()
        return True
    except Exception:
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
