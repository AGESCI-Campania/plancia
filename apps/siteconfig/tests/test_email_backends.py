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
