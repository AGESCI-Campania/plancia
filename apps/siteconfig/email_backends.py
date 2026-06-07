# apps/siteconfig/email_backends.py
"""Backend email che supporta SMTP, provider transazionali e Gmail OAuth2.

Routing per tipo di invio:
  standard  → email_backend_standard (default: SMTP)
  massivo   → email_backend_massivo  (default: provider transazionale)

email_mode sovrascrive il routing:
  MAILPIT           → entrambi i tipi vanno a Mailpit
  SIMULATO          → scrive su file, non invia
  SIMULATO_PIU_INVIO → scrive su file E invia via backend configurato
  REALE             → usa il routing per tipo
"""
from __future__ import annotations

import base64
import logging
import smtplib

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

_PROVIDER_ANYMAIL_KEY = {
    "brevo": "BREVO_API_KEY",
    "mailgun": "MAILGUN_API_KEY",
    "mailersend": "MAILERSEND_API_TOKEN",
    "postmark": "POSTMARK_SERVER_TOKEN",
    "sendgrid": "SENDGRID_API_KEY",
    "sparkpost": "SPARKPOST_API_KEY",
    "ses": None,
}

_PROVIDER_WEBHOOK_KEY = {
    "brevo": "BREVO_WEBHOOK_SECRET",
    "mailgun": "MAILGUN_WEBHOOK_SIGNING_KEY",
    "mailersend": "MAILERSEND_SIGNING_SECRET",
    "postmark": "POSTMARK_WEBHOOK_TOKEN",
    "sendgrid": "SENDGRID_WEBHOOK_VERIFICATION_KEY",
    "sparkpost": None,
    "ses": None,
}

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
    """Costruisce il dict ANYMAIL dalle impostazioni DB."""
    provider = imp.email_provider
    result = dict(getattr(settings, "ANYMAIL", {}))
    api_key_setting = _PROVIDER_ANYMAIL_KEY.get(provider)
    if api_key_setting and imp.email_provider_api_key:
        result[api_key_setting] = imp.email_provider_api_key
    webhook_key_setting = _PROVIDER_WEBHOOK_KEY.get(provider)
    if webhook_key_setting and imp.email_provider_webhook_secret:
        result[webhook_key_setting] = imp.email_provider_webhook_secret
    return result


# ---------------------------------------------------------------------------
# Gmail OAuth2 SMTP
# ---------------------------------------------------------------------------

def _get_gmail_access_token(creds) -> str:
    """Recupera o rinnova il token di accesso Gmail via OAuth2."""
    from django.utils import timezone

    if not creds.scaduto:
        return creds.access_token

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials as GoogleCredentials
    except ImportError as exc:
        raise ImportError(
            "google-auth è necessario per Gmail OAuth. "
            "Esegui: uv add google-auth google-auth-oauthlib"
        ) from exc

    goog_creds = GoogleCredentials(
        token=creds.access_token or None,
        refresh_token=creds.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
    )
    goog_creds.refresh(Request())

    creds.access_token = goog_creds.token
    if goog_creds.expiry:
        expires = goog_creds.expiry
        expires = timezone.make_aware(expires) if expires.tzinfo is None else expires
        creds.expires_at = expires
    creds.save(update_fields=["access_token", "expires_at", "aggiornato_at"])
    return creds.access_token


class GmailOAuth2Backend(SmtpBackend):
    """Backend SMTP Gmail con autenticazione XOAUTH2 (OAuth2).

    Usa GOOGLE_OAUTH_CLIENT_ID/SECRET per rinnovare il token.
    Richiede che Impostazioni.smtp_gmail_account sia valorizzato
    e GmailSMTPCredenziali contenga il refresh_token.
    """

    def open(self):
        if self.connection:
            return False

        from apps.siteconfig.models import GmailSMTPCredenziali, Impostazioni

        imp = Impostazioni.get()
        try:
            creds = GmailSMTPCredenziali.objects.get(account_email=imp.smtp_gmail_account)
        except GmailSMTPCredenziali.DoesNotExist:
            raise ValueError(
                "Credenziali Gmail OAuth non trovate. "
                "Collega un account Gmail nelle impostazioni SMTP."
            ) from None

        access_token = _get_gmail_access_token(creds)

        try:
            conn = smtplib.SMTP("smtp.gmail.com", 587, timeout=self.timeout)
            conn.ehlo()
            conn.starttls()
            conn.ehlo()
            # smtplib.auth() chiama b2a_base64() sul valore restituito dall'authobject,
            # provocando doppia codifica. Usiamo docmd() con il base64 già calcolato.
            auth_string = f"user={creds.account_email}\x01auth=Bearer {access_token}\x01\x01"
            auth_b64 = base64.b64encode(auth_string.encode("ascii")).decode("ascii")
            code, resp = conn.docmd("AUTH", f"XOAUTH2 {auth_b64}")
            if code != 235:
                raise smtplib.SMTPAuthenticationError(code, resp)
            self.connection = conn
            return True
        except Exception:
            if not self.fail_silently:
                raise
            return False


# ---------------------------------------------------------------------------
# Backend factory helpers
# ---------------------------------------------------------------------------

def _smtp_backend(imp, fail_silently: bool = False) -> BaseEmailBackend:
    """Restituisce il backend SMTP configurato (password o Gmail OAuth)."""
    if imp.smtp_use_gmail_oauth:
        return GmailOAuth2Backend(fail_silently=fail_silently)
    return SmtpBackend(
        host=imp.smtp_host or settings.EMAIL_HOST,
        port=imp.smtp_port or settings.EMAIL_PORT,
        username=imp.smtp_user or settings.EMAIL_HOST_USER,
        password=imp.smtp_password or settings.EMAIL_HOST_PASSWORD,
        use_tls=imp.smtp_use_tls,
        fail_silently=fail_silently,
    )


class _AnymailBackend(BaseEmailBackend):
    """Wrapper anymail che applica l'override settings al momento dell'invio."""

    def __init__(self, backend_path: str, anymail_settings: dict, fail_silently: bool = False):
        self._backend_path = backend_path
        self._anymail_settings = anymail_settings
        super().__init__(fail_silently=fail_silently)

    def send_messages(self, messages):
        try:
            with override_settings(ANYMAIL=self._anymail_settings):
                backend_cls = import_string(self._backend_path)
                backend = backend_cls(fail_silently=self.fail_silently)
                return backend.send_messages(messages) or 0
        except Exception:
            logger.exception("Errore invio anymail (%s)", self._backend_path)
            if not self.fail_silently:
                raise
            return 0


def _transazionale_backend(imp, fail_silently: bool = False) -> BaseEmailBackend:
    """Restituisce il backend provider transazionale configurato."""
    from apps.siteconfig.models import EmailProvider

    if imp.email_provider == EmailProvider.SMTP:
        logger.warning("email_backend=transazionale ma email_provider=smtp: fallback a SMTP")
        return _smtp_backend(imp, fail_silently)

    backend_path = _PROVIDER_BACKEND.get(imp.email_provider)
    if not backend_path:
        logger.error("Provider anymail non supportato: %s — fallback a SMTP", imp.email_provider)
        return _smtp_backend(imp, fail_silently)

    return _AnymailBackend(
        backend_path=backend_path,
        anymail_settings=build_anymail_settings(imp),
        fail_silently=fail_silently,
    )


class _TeeBackend(BaseEmailBackend):
    """Invia via più backend contemporaneamente (usato per SIMULATO_PIU_INVIO)."""

    def __init__(self, backends: list, fail_silently: bool = False):
        self._backends = backends
        super().__init__(fail_silently=fail_silently)

    def send_messages(self, messages):
        sent = 0
        for backend in self._backends:
            try:
                sent = max(sent, backend.send_messages(messages) or 0)
            except Exception:
                logger.exception("_TeeBackend: errore backend %s", backend.__class__.__name__)
                if not self.fail_silently:
                    raise
        return sent


# ---------------------------------------------------------------------------
# Routing pubblico
# ---------------------------------------------------------------------------

def get_connection_per_tipo(tipo: str = "standard", fail_silently: bool = False) -> BaseEmailBackend:
    """Restituisce una connessione mail per il tipo di invio.

    tipo: 'standard' | 'massivo'
    Rispetta email_mode: MAILPIT e SIMULATO sovrascrivono entrambi i tipi.
    """
    from apps.siteconfig.models import BackendPosta, EmailMode, Impostazioni

    imp = Impostazioni.get()

    if imp.email_mode == EmailMode.SIMULATO:
        return FileBackend(
            file_path=str(settings.EMAIL_FILE_PATH),
            fail_silently=fail_silently,
        )

    if imp.email_mode == EmailMode.MAILPIT:
        return SmtpBackend(
            host=getattr(settings, "MAILPIT_SMTP_HOST", "localhost"),
            port=getattr(settings, "MAILPIT_SMTP_PORT", 1025),
            use_tls=False,
            fail_silently=fail_silently,
        )

    # REALE o SIMULATO_PIU_INVIO
    backend_key = (
        imp.email_backend_massivo if tipo == "massivo"
        else imp.email_backend_standard
    )
    real = (
        _transazionale_backend(imp, fail_silently)
        if backend_key == BackendPosta.TRANSAZIONALE
        else _smtp_backend(imp, fail_silently)
    )

    if imp.email_mode == EmailMode.SIMULATO_PIU_INVIO:
        file_conn = FileBackend(file_path=str(settings.EMAIL_FILE_PATH), fail_silently=True)
        # L'invio reale è best-effort: gli errori vengono loggati ma non propagati
        # (il file simulato viene sempre scritto).
        return _TeeBackend([file_conn, real], fail_silently=True)

    return real


# ---------------------------------------------------------------------------
# Backend globale (EMAIL_BACKEND) — usato da allauth, sistema, ecc.
# ---------------------------------------------------------------------------

class PlanciaEmailBackend(BaseEmailBackend):
    """Backend globale: legge email_mode e instrada a SMTP o provider transazionale."""

    def send_messages(self, email_messages):
        conn = get_connection_per_tipo("standard", fail_silently=self.fail_silently)
        return conn.send_messages(email_messages)
