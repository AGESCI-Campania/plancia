"""Percorsi serviti da Django dopo il passaggio alla SPA: pagine d'errore statiche,
manutenzione, CSP, URL rimasti e rimossi."""
from pathlib import Path

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import NoReverseMatch, resolve, reverse

from apps.accounts.models import Ruolo, User

TEMPLATES = Path(settings.BASE_DIR) / "templates"


@pytest.mark.parametrize(
    "nome", ["403.html", "404.html", "500.html", "403_csrf.html", "403_mfa.html",
             "siteconfig/manutenzione.html"],
)
def test_pagine_errore_autonome(nome):
    """HTML statico: niente ereditarietà, tag o statici del tema (devono reggere anche a DB giù)."""
    testo = (TEMPLATES / nome).read_text()
    assert testo.startswith("<!doctype html>")
    assert "{% extends" not in testo and "{% load" not in testo and "{% include" not in testo
    assert "<style>" in testo and "/static/" not in testo


@pytest.mark.django_db
class TestErrori:
    def test_404_django_html(self, client):
        r = client.get("/percorso-inesistente/")
        assert r.status_code == 404
        assert r["Content-Type"].startswith("text/html")
        assert b"Pagina non trovata" in r.content

    def test_404_api_json(self, client):
        r = client.get("/api/v1/percorso-inesistente/xyz")
        assert r.status_code == 404
        assert r["Content-Type"] == "application/json"

    def test_csrf_html_e_json(self, rf):
        from config.error_views import csrf_failure

        r = csrf_failure(rf.post("/admin/login/"), reason="x")
        assert r.status_code == 403 and b"Errore di sicurezza" in r.content
        r = csrf_failure(rf.post("/api/v1/edizioni"), reason="x")
        assert r.status_code == 403 and r["Content-Type"] == "application/json"

    def test_500(self, rf):
        from config.error_views import server_error

        r = server_error(rf.get("/admin/"))
        assert r.status_code == 500 and b"Si \xc3\xa8 verificato un errore" in r.content
        r = server_error(rf.get("/api/v1/me"))
        assert r.status_code == 500 and r["Content-Type"] == "application/json"


@pytest.mark.django_db
class TestManutenzione:
    @pytest.fixture(autouse=True)
    def _manutenzione(self):
        from apps.siteconfig.manutenzione import imposta_manutenzione

        imposta_manutenzione(True, "Aggiornamento alla 3.0 in corso.")
        yield
        imposta_manutenzione(False)

    def _utente(self, ruolo=Ruolo.CRP, **extra) -> User:
        return User.objects.create_user(
            username=f"{ruolo}@t.it", email=f"{ruolo}@t.it", password="x", ruolo=ruolo, **extra
        )

    def test_percorso_django_pagina_statica(self, client):
        client.force_login(self._utente())
        r = client.get("/celery/")
        assert r.status_code == 503
        assert r["Content-Type"].startswith("text/html")
        assert b"Aggiornamento alla 3.0 in corso." in r.content

    def test_api_json(self, client):
        r = client.get("/api/v1/edizioni")
        assert r.status_code == 503
        assert r.json() == {"detail": "Aggiornamento alla 3.0 in corso.", "maintenance": True}

    def test_sito_e_healthz_raggiungibili(self, client):
        assert client.get("/api/v1/sito").status_code == 200
        assert client.get("/healthz/").status_code == 200

    def test_admin_per_ruolo_passa(self, client):
        # Admin per nomina o da Sestante (non superuser): usa Plancia durante la manutenzione
        client.force_login(self._utente(Ruolo.ADMIN))
        assert client.get("/api/v1/me").status_code == 200
        client.force_login(self._utente(Ruolo.SEGRETERIA))
        assert client.get("/api/v1/me").status_code == 503

    def test_login_headless_aperto(self, client):
        # Senza il login dalla SPA nemmeno un Admin potrebbe entrare
        assert client.get("/_allauth/browser/v1/config").status_code == 200


@pytest.mark.django_db
def test_csp_inviata_dal_middleware(client):
    politica = {"default-src": ["'self'"], "frame-ancestors": ["'none'"]}
    with override_settings(SECURE_CSP=politica):
        r = client.get("/admin/login/")
    assert r["Content-Security-Policy"] == "default-src 'self'; frame-ancestors 'none'"


@pytest.mark.django_db
def test_proxy_csp_larga_e_solo_admin(client):
    from unittest import mock

    segreteria = User.objects.create_user(
        username="s@t.it", email="s@t.it", password="x", ruolo=Ruolo.SEGRETERIA
    )
    client.force_login(segreteria)
    with mock.patch("apps.accounts.middleware.mfa_da_configurare", return_value=False):
        assert client.get("/mailadmin/").status_code == 403  # solo Admin
    client.logout()
    r = client.get("/celery/")
    assert r.status_code == 302 and r["Location"] == "/accesso?next=%2Fcelery%2F"


class TestUrl:
    @pytest.mark.parametrize("percorso", [
        "/healthz/", "/admin/", "/drive/oauth/callback/", "/impostazioni/gmail-smtp/oauth/callback/",
        "/anymail/webhook/", "/mailadmin/", "/celery/x", "/_allauth/browser/v1/auth/session",
        "/api/v1/sito",
    ])
    def test_percorsi_rimasti(self, percorso):
        resolve(percorso)

    @pytest.mark.parametrize("nome", [
        "home", "diaries:list", "editions:list", "siteconfig:impostazioni", "hijack:acquire",
        "account_login", "accounts:profilo",
    ])
    def test_interfaccia_django_rimossa(self, nome):
        with pytest.raises(NoReverseMatch):
            reverse(nome)

    def test_endpoint_pwa_2x_rimossi(self):
        from django.urls import Resolver404

        for percorso in ("/api/diari/1/anagrafica/", "/api/soci/"):
            with pytest.raises(Resolver404):
                resolve(percorso)
