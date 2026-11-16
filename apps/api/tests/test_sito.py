"""API sito pubblico: titolo, footer, pagine, manutenzione, login, versione."""
from __future__ import annotations

import tomllib

import pytest
from django.conf import settings
from django.core.cache import cache

from apps.siteconfig.manutenzione import MESSAGGIO_PREDEFINITO, imposta_manutenzione
from apps.siteconfig.models import FooterLink, Impostazioni, PaginaStatica

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cache_pulita():
    """Impostazioni sta in cache: non deve sopravvivere al rollback del test."""
    cache.clear()
    yield
    cache.clear()


def _versione_pyproject() -> str:
    with open(settings.BASE_DIR / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def test_sito_anonimo(client_di):
    imp, _ = Impostazioni.objects.get_or_create(pk=1)
    imp.titolo = "Plancia Test"
    imp.footer_testo = "{{ titolo }} v{{ versione }}"
    imp.save()
    FooterLink.objects.create(impostazioni=imp, tipo="email", url="mailto:a@b.it", ordine=1)
    FooterLink.objects.create(impostazioni=imp, tipo="sito_web", url="https://x.it",
                              etichetta="Sito", ordine=2)

    r = client_di("anonimo").get("/api/v1/sito")
    assert r.status_code == 200, r.content
    dati = r.json()
    assert dati["titolo"] == "Plancia Test"
    assert dati["versione"] == _versione_pyproject()
    assert dati["footer"]["testo"] == f"Plancia Test v{_versione_pyproject()}"
    assert dati["footer"]["links"] == [
        {"tipo": "email", "url": "mailto:a@b.it", "etichetta": "Email"},
        {"tipo": "sito_web", "url": "https://x.it", "etichetta": "Sito"},
    ]
    assert {p["slug"] for p in dati["pagine"]} == {"privacy", "termini"}
    assert dati["manutenzione"] == {"attiva": False, "messaggio": ""}
    assert dati["login"]["locale"] is True
    assert isinstance(dati["login"]["provider"], list)


def test_sito_provider_configurati(client_di, settings):
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {"APP": {"client_id": "id-finto", "secret": "s", "key": ""}},
    }
    r = client_di("anonimo").get("/api/v1/sito")
    assert {"id": "google", "nome": "Google"} in r.json()["login"]["provider"]

    settings.SOCIALACCOUNT_PROVIDERS = {}
    r = client_di("anonimo").get("/api/v1/sito")
    assert all(p["id"] != "google" for p in r.json()["login"]["provider"])


def test_sito_in_manutenzione(client_di):
    imposta_manutenzione(True, "Torniamo alle 18")
    r = client_di("anonimo").get("/api/v1/sito")
    assert r.status_code == 200
    assert r.json()["manutenzione"] == {"attiva": True, "messaggio": "Torniamo alle 18"}
    # gli altri endpoint per i non Admin rispondono 503 JSON
    r = client_di("crp").get("/api/v1/me")
    assert r.status_code == 503
    assert r.json() == {"detail": "Torniamo alle 18", "maintenance": True}

    imposta_manutenzione(True, "")
    r = client_di("anonimo").get("/api/v1/sito")
    assert r.json()["manutenzione"]["messaggio"] == MESSAGGIO_PREDEFINITO


def test_pagina_statica(client_di):
    r = client_di("anonimo").get("/api/v1/sito/pagine/privacy")
    assert r.status_code == 200
    assert r.json()["titolo"] == "Privacy Policy"
    assert r.json()["aggiornato_at"] is None

    PaginaStatica.objects.create(slug="termini", titolo="Termini", contenuto="<p>Ok</p>")
    r = client_di("anonimo").get("/api/v1/sito/pagine/termini")
    assert r.json()["contenuto"] == "<p>Ok</p>"
    assert client_di("anonimo").get("/api/v1/sito/pagine/boh").status_code == 404
