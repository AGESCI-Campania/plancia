# apps/siteconfig/email_backends.py
"""Backend email che rispetta Impostazioni.email_mode (docs sez. 15):

- reale               -> invia via SMTP
- simulato            -> NON invia: scrive ogni messaggio in logs/email/ (.eml)
- simulato_piu_invio  -> scrive il log E invia via SMTP
"""
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.filebased import EmailBackend as FileBackend
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend


class PlanciaEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        # import locale per evitare problemi all'avvio/migrazioni
        from apps.siteconfig.models import EmailMode, Impostazioni

        imp = Impostazioni.get()
        sent = 0

        if imp.email_mode in (EmailMode.SIMULATO, EmailMode.SIMULATO_PIU_INVIO):
            fb = FileBackend(file_path=str(settings.EMAIL_FILE_PATH))
            sent = fb.send_messages(email_messages)

        if imp.email_mode in (EmailMode.REALE, EmailMode.SIMULATO_PIU_INVIO):
            smtp = SmtpBackend(
                host=imp.smtp_host or settings.EMAIL_HOST,
                port=imp.smtp_port or settings.EMAIL_PORT,
                username=imp.smtp_user or settings.EMAIL_HOST_USER,
                password=imp.smtp_password or settings.EMAIL_HOST_PASSWORD,
                use_tls=imp.smtp_use_tls,
            )
            sent = smtp.send_messages(email_messages)

        return sent
