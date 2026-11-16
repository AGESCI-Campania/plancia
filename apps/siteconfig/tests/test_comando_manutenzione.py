"""Comando `manage.py manutenzione attiva|disattiva|stato` (usato da scripts/aggiorna.sh)."""
from __future__ import annotations

from io import StringIO

import pytest
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import Client

from apps.siteconfig.models import Impostazioni

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cache_pulita():
    cache.clear()
    yield
    cache.clear()


def _esegui(*args: str) -> str:
    out = StringIO()
    call_command("manutenzione", *args, stdout=out)
    return out.getvalue().strip()


def test_stato_iniziale_disattiva():
    assert _esegui("stato") == "disattiva"


def test_attiva_e_disattiva():
    assert _esegui("attiva", "--messaggio", "Aggiornamento a v3.0.0") == "attiva"
    assert _esegui("stato") == "attiva"
    imp = Impostazioni.objects.get(pk=1)
    assert imp.manutenzione is True
    assert imp.manutenzione_messaggio == "Aggiornamento a v3.0.0"
    # stesso flag del middleware (la cache è aggiornata dal save)
    assert Impostazioni.get().manutenzione is True
    r = Client().get("/api/v1/edizioni")
    assert r.status_code == 503 and r.json()["maintenance"] is True

    assert _esegui("disattiva") == "disattiva"
    assert _esegui("stato") == "disattiva"
    assert Impostazioni.get().manutenzione is False
    # il messaggio resta per la prossima volta
    assert Impostazioni.objects.get(pk=1).manutenzione_messaggio == "Aggiornamento a v3.0.0"


def test_non_sovrascrive_le_altre_impostazioni():
    imp, _ = Impostazioni.objects.get_or_create(pk=1)
    Impostazioni.get()  # copia in cache
    Impostazioni.objects.filter(pk=1).update(titolo="Nuovo titolo")
    _esegui("attiva")
    assert Impostazioni.objects.get(pk=1).titolo == "Nuovo titolo"


def test_azione_non_valida():
    with pytest.raises(CommandError):
        call_command("manutenzione", "boh")
