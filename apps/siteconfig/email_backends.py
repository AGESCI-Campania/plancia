# apps/siteconfig/email_backends.py
"""Backend email che rispetta Impostazioni.email_mode e Impostazioni.email_provider.

Modalità (email_mode):
- reale               -> invia via provider configurato (SMTP o transazionale)
- simulato            -> NON invia: scrive ogni messaggio in logs/email/ (.eml)
- simulato_piu_invio  -> scrive il log E invia

Provider transazionali (email_provider != smtp):
- Usa django-anymail con API key letta da DB (thread-safe con Gunicorn sync workers).
- Supportati: Brevo, Mailgun, MailerSend, Postmark, SendGrid, SparkPost, Amazon SES.
"""
import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.filebased import EmailBackend as FileBackend
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend
from django.test.utils import override_settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

_PROVIDER_BACKEND = {
    "brevo": "anymail.backends.brevo.EmailBackend",
    "mailgun": "anymail.backends.mailgun.EmailBackend",
    "mailersend": "anymail.backends.mailersend.EmailBackend",
    "postmark": "anymail.backends.postmark.EmailBackend",
    "sendgrid": "anymail.backends.sendgrid.EmailBackend",
    "sparkpost": "anymail.backends.sparkpost.EmailBackend",
    "ses": "anymail.backends.amazon_ses.EmailBackend",
}

# Chiave nel dict ANYMAIL corrispondente all'API key del provider
_PROVIDER_ANYMAIL_KEY = {
    "brevo": "BREVO_API_KEY",
    "mailgun": "MAILGUN_API_KEY",
    "mailersend": "MAILERSEND_API_TOKEN",
    "postmark": "POSTMARK_SERVER_TOKEN",
    "sendgrid": "SENDGRID_API_KEY",
    "sparkpost": "SPARKPOST_API_KEY",
    "ses": None,  # usa boto3/IAM
}

# Chiave nel dict ANYMAIL corrispondente al webhook secret del provider
_PROVIDER_WEBHOOK_KEY = {
    "brevo": "BREVO_WEBHOOK_SECRET",
    "mailgun": "MAILGUN_WEBHOOK_SIGNING_KEY",
    "mailersend": "MAILERSEND_SIGNING_SECRET",
    "postmark": "POSTMARK_WEBHOOK_TOKEN",
    "sendgrid": "SENDGRID_WEBHOOK_VERIFICATION_KEY",
    "sparkpost": None,
    "ses": None,
}

# Modulo e classe per il webhook receiver di ciascun provider
PROVIDER_WEBHOOK_VIEW = {
    "brevo": ("anymail.webhooks.brevo", "BrevoTrackingWebhookView"),
    "mailgun": ("anymail.webhooks.mailgun", "MailgunTrackingWebhookView"),
    "mailersend": ("anymail.webhooks.mailersend", "MailerSendTrackingWebhookView"),
    "postmark": ("anymail.webhooks.postmark", "PostmarkTrackingWebhookView"),
    "sendgrid": ("anymail.webhooks.sendgrid", "SendGridTrackingWebhookView"),
    "sparkpost": ("anymail.webhooks.sparkpost", "SparkPostTrackingWebhookView"),
    "ses": ("anymail.webhooks.amazon_ses", "AmazonSESTrackingWebhookView"),
}


def build_anymail_settings(imp) -> dict:
    """Costruisce il dict ANYMAIL dalle impostazioni DB, partendo dai default in settings.py."""
    provider = imp.email_provider
    result = dict(getattr(settings, "ANYMAIL", {}))

    api_key_setting = _PROVIDER_ANYMAIL_KEY.get(provider)
    if api_key_setting and imp.email_provider_api_key:
        result[api_key_setting] = imp.email_provider_api_key

    webhook_key_setting = _PROVIDER_WEBHOOK_KEY.get(provider)
    if webhook_key_setting and imp.email_provider_webhook_secret:
        result[webhook_key_setting] = imp.email_provider_webhook_secret

    return result


class PlanciaEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        # import locale per evitare problemi all'avvio/migrazioni
        from apps.siteconfig.models import EmailMode, EmailProvider, Impostazioni

        imp = Impostazioni.get()
        sent = 0

        if imp.email_mode in (EmailMode.SIMULATO, EmailMode.SIMULATO_PIU_INVIO):
            fb = FileBackend(file_path=str(settings.EMAIL_FILE_PATH))
            sent = fb.send_messages(email_messages)

        if imp.email_mode == EmailMode.MAILPIT:
            smtp = SmtpBackend(
                host=settings.MAILPIT_SMTP_HOST,
                port=settings.MAILPIT_SMTP_PORT,
                use_tls=False,
            )
            sent = smtp.send_messages(email_messages)

        elif imp.email_mode in (EmailMode.REALE, EmailMode.SIMULATO_PIU_INVIO):
            if imp.email_provider == EmailProvider.SMTP:
                smtp = SmtpBackend(
                    host=imp.smtp_host or settings.EMAIL_HOST,
                    port=imp.smtp_port or settings.EMAIL_PORT,
                    username=imp.smtp_user or settings.EMAIL_HOST_USER,
                    password=imp.smtp_password or settings.EMAIL_HOST_PASSWORD,
                    use_tls=imp.smtp_use_tls,
                )
                sent = smtp.send_messages(email_messages)
            else:
                sent = self._send_via_anymail(email_messages, imp)

        return sent

    def _send_via_anymail(self, messages, imp):
        """Invia via anymail con impostazioni lette da DB.

        Usa override_settings come context manager: thread-safe con Gunicorn sync workers.
        """
        provider = imp.email_provider
        backend_path = _PROVIDER_BACKEND.get(provider)
        if not backend_path:
            logger.error("Provider anymail non supportato: %s", provider)
            return 0

        anymail_settings = build_anymail_settings(imp)
        try:
            with override_settings(ANYMAIL=anymail_settings):
                backend_cls = import_string(backend_path)
                backend = backend_cls(fail_silently=self.fail_silently)
                return backend.send_messages(messages) or 0
        except Exception:
            logger.exception("Errore invio anymail (provider=%s)", provider)
            if not self.fail_silently:
                raise
            return 0
