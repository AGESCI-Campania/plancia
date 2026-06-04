# apps/notifications/webhooks.py
"""Signal handlers anymail per il tracking delle email inviate (bounce, consegna, spam).

Registrati in NotificationsConfig.ready(). Richiedono django-anymail installato
e un provider transazionale configurato in Impostazioni.

Webhook URL da configurare nel provider: /anymail/webhook/
"""
import logging
from importlib import import_module

from django.http import HttpResponseNotFound
from django.test.utils import override_settings
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Anymail signal handlers
# ---------------------------------------------------------------------------

def _invito_da_messaggio(message):
    """Restituisce il pk dell'Invito dal campo metadata del messaggio, se presente."""
    metadata = getattr(message, "metadata", None) or {}
    return metadata.get("invito_pk")


def handle_post_send(sender, message, status, esp_response, **kwargs):
    """Cattura il provider_message_id dopo l'invio e aggiorna il delivery_status."""
    invito_pk = _invito_da_messaggio(message)
    if not invito_pk:
        return

    try:
        from apps.notifications.models import DeliveryStatus, Invito

        invito = Invito.objects.filter(pk=invito_pk).first()
        if not invito:
            return

        msg_id = status.message_id
        if isinstance(msg_id, dict):
            # anymail a volte restituisce {recipient: message_id} per invii batch
            msg_id = next(iter(msg_id.values()), "")

        invito.provider_message_id = msg_id or ""
        invito.delivery_status = DeliveryStatus.INVIATO
        invito.save(update_fields=["provider_message_id", "delivery_status"])
    except Exception:
        logger.exception("Errore aggiornamento provider_message_id invito pk=%s", invito_pk)


def handle_tracking(sender, event, esp_response, **kwargs):
    """Aggiorna lo stato di consegna dell'Invito in base all'evento anymail."""
    # Priorità: invito_pk da metadata (più affidabile dell'event.message_id)
    invito_pk = (event.metadata or {}).get("invito_pk") if event.metadata else None

    try:
        from apps.notifications.models import DeliveryStatus, Invito

        invito = None
        if invito_pk:
            invito = Invito.objects.filter(pk=invito_pk).first()
        if invito is None and event.message_id:
            invito = Invito.objects.filter(provider_message_id=event.message_id).first()
        if invito is None:
            return

        _EVENT_STATUS_MAP = {
            "bounced": DeliveryStatus.BOUNCE,
            "complained": DeliveryStatus.SPAM,
            "delivered": DeliveryStatus.CONSEGNATO,
            "failed": DeliveryStatus.FALLITO,
        }
        new_status = _EVENT_STATUS_MAP.get(event.event_type)
        if new_status is None:
            return  # opened, clicked, ecc. non influenzano lo stato

        invito.delivery_status = new_status
        description = (
            getattr(event, "reject_reason", "") or
            getattr(event, "description", "") or
            getattr(event, "mta_response", "") or ""
        )
        invito.delivery_error = str(description)[:500]
        invito.save(update_fields=["delivery_status", "delivery_error"])
    except Exception:
        logger.exception(
            "Errore aggiornamento delivery_status invito pk=%s message_id=%s",
            invito_pk, getattr(event, "message_id", None),
        )


# ---------------------------------------------------------------------------
# Webhook dispatcher view
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name="dispatch")
class AnymailWebhookDispatchView(View):
    """Riceve gli eventi di tracking dal provider transazionale configurato in DB.

    URL unico da configurare nel provider: /anymail/webhook/
    Il dispatcher determina il provider dalle Impostazioni e instrada al relativo handler.
    """

    def post(self, request, *args, **kwargs):
        from apps.siteconfig.email_backends import PROVIDER_WEBHOOK_VIEW, build_anymail_settings
        from apps.siteconfig.models import EmailProvider, Impostazioni

        imp = Impostazioni.get()
        if imp.email_provider == EmailProvider.SMTP:
            return HttpResponseNotFound()

        provider = imp.email_provider
        if provider not in PROVIDER_WEBHOOK_VIEW:
            return HttpResponseNotFound()

        module_path, view_name = PROVIDER_WEBHOOK_VIEW[provider]
        try:
            mod = import_module(module_path)
        except ImportError:
            logger.error("Modulo anymail non trovato per provider: %s", provider)
            return HttpResponseNotFound()

        view_cls = getattr(mod, view_name, None)
        if view_cls is None:
            logger.error("View anymail %s non trovata in %s", view_name, module_path)
            return HttpResponseNotFound()

        anymail_settings = build_anymail_settings(imp)
        with override_settings(ANYMAIL=anymail_settings):
            return view_cls.as_view()(request, *args, **kwargs)
