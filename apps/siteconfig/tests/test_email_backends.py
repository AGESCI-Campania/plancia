"""Routing delle email tramite gli alias MAILERS (Django 6.1)."""

import warnings

import pytest
from django.core.mail import EmailMessage
from django.test import override_settings

from apps.siteconfig.email_backends import PlanciaEmailBackend
from apps.siteconfig.models import EmailMode, Impostazioni

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("tipo", ["standard", "massivo"])
def test_modalita_simulata_scrive_su_file_senza_avvisi_di_deprecazione(tmp_path, tipo):
    imp = Impostazioni.get()
    imp.email_mode = EmailMode.SIMULATO
    imp.save()
    msg = EmailMessage("Oggetto", "Corpo", "da@example.org", ["a@example.org"])
    with override_settings(EMAIL_SIMULATO_DIR=tmp_path), warnings.catch_warnings():
        warnings.simplefilter("error")
        inviati = PlanciaEmailBackend(tipo=tipo, alias=tipo).send_messages([msg])
    assert inviati == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_mailers_hanno_gli_alias_di_plancia(settings):
    assert {"default", "standard", "massivo"} <= set(settings.MAILERS)


class _SMTPFinto:
    """Registra i parametri di connessione al posto di smtplib.SMTP."""

    connessioni: list[dict] = []

    def __init__(self, host, port, local_hostname=None, **kwargs):
        _SMTPFinto.connessioni.append(
            {"host": host, "port": port, "local_hostname": local_hostname, **kwargs}
        )

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def quit(self):
        pass


def _apri_smtp(monkeypatch):
    from django.core.mail.backends import smtp

    from apps.siteconfig.email_backends import _smtp_backend

    _SMTPFinto.connessioni = []
    monkeypatch.setattr(smtp.smtplib, "SMTP", _SMTPFinto)
    imp = Impostazioni.get()
    imp.smtp_host, imp.smtp_port, imp.smtp_use_tls = "smtps.aruba.it", 587, True
    backend = _smtp_backend(imp)
    backend.open()
    backend.close()
    return _SMTPFinto.connessioni[0]


def test_ehlo_configurabile(monkeypatch, settings):
    settings.SMTP_EHLO = "plancia.agescicampania.net"
    connessione = _apri_smtp(monkeypatch)
    assert connessione["local_hostname"] == "plancia.agescicampania.net"
    assert (connessione["host"], connessione["port"]) == ("smtps.aruba.it", 587)


def test_ehlo_di_default(monkeypatch, settings):
    from django.core.mail.utils import DNS_NAME

    settings.SMTP_EHLO = ""
    assert _apri_smtp(monkeypatch)["local_hostname"] == DNS_NAME.get_fqdn()
