"""API helpdesk: visibilità dei ticket per ruolo e azioni."""
from __future__ import annotations

import pytest

from apps.api.tests.conftest import json_body
from apps.helpdesk.models import RispostaTicket, StatoTicket, Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cache_pulita():
    """Il rate limiting API conta le richieste in cache (per IP): azzerala a ogni test,
    altrimenti nella suite completa si superano le 60 richieste/minuto (429)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()

STAFF = ("admin", "segreteria", "incaricato_eg")


@pytest.fixture
def ticket_csq(utenti, diario):
    return Ticket.objects.create(
        aperto_da=utenti["csq"], diario=diario, oggetto="Non salva", corpo="Il modulo 2...",
        categoria="tecnico",
    )


@pytest.fixture
def ticket_crp(utenti):
    return Ticket.objects.create(
        aperto_da=utenti["crp"], oggetto="Accesso", corpo="Non entro", categoria="accesso",
    )


# ── Lista e dettaglio ───────────────────────────────────────────────────────


def test_utente_vede_solo_i_propri(client_di, ticket_csq, ticket_crp):
    r = client_di("csq").get("/api/v1/helpdesk")
    assert r.status_code == 200
    assert [t["id"] for t in r.json()["items"]] == [ticket_csq.pk]
    assert r.json()["items"][0]["diario"]["squadriglia"] == "Tigri"
    assert client_di("estraneo").get("/api/v1/helpdesk").json()["count"] == 0


@pytest.mark.parametrize("ruolo", STAFF)
def test_staff_vede_tutti(client_di, ticket_csq, ticket_crp, ruolo):
    r = client_di(ruolo).get("/api/v1/helpdesk")
    assert r.json()["count"] == 2
    r = client_di(ruolo).get("/api/v1/helpdesk", {"stato": "aperto"})
    assert r.json()["count"] == 2
    r = client_di(ruolo).get("/api/v1/helpdesk", {"stato": "chiuso"})
    assert r.json()["count"] == 0


def test_anonimo(client_di):
    assert client_di("anonimo").get("/api/v1/helpdesk").status_code == 401
    assert client_di("anonimo").post(
        "/api/v1/helpdesk", **json_body({"oggetto": "x", "corpo": "y", "categoria": "altro"})
    ).status_code == 401


def test_dettaglio_permessi(client_di, ticket_csq):
    url = f"/api/v1/helpdesk/{ticket_csq.pk}"
    r = client_di("csq").get(url)
    assert r.status_code == 200
    assert r.json()["azioni"] == {"rispondi": True, "prendi_in_carico": False, "chiudi": True}
    assert client_di("segreteria").get(url).json()["azioni"]["prendi_in_carico"] is True
    assert client_di("estraneo").get(url).status_code == 403
    assert client_di("pgv").get(url).status_code == 403
    assert client_di("csq").get("/api/v1/helpdesk/999999").status_code == 404


# ── Apertura ────────────────────────────────────────────────────────────────


def test_crea_ticket_con_diario(client_di, utenti, diario):
    r = client_di("csq").post("/api/v1/helpdesk", **json_body({
        "oggetto": "Aiuto", "corpo": "Testo", "categoria": "compilazione", "diario_id": diario.pk,
    }))
    assert r.status_code == 201, r.content
    t = Ticket.objects.get(pk=r.json()["id"])
    assert t.aperto_da == utenti["csq"] and t.diario == diario
    assert r.json()["risposte"] == []


def test_crea_ticket_diario_altrui(client_di, diario):
    # l'estraneo non è Capo Squadriglia di quel diario; la Pattuglia GV non ha diari collegabili
    for ruolo in ("estraneo", "pgv"):
        r = client_di(ruolo).post("/api/v1/helpdesk", **json_body({
            "oggetto": "x", "corpo": "y", "categoria": "altro", "diario_id": diario.pk,
        }))
        assert r.status_code == 422
        assert "diario" in r.json()["errori"]
    assert not Ticket.objects.exists()


def test_crea_ticket_validazione(client_di):
    r = client_di("crp").post("/api/v1/helpdesk", **json_body({
        "oggetto": " ", "corpo": "", "categoria": "boh",
    }))
    assert r.status_code == 422
    assert set(r.json()["errori"]) == {"oggetto", "corpo", "categoria"}


def test_opzioni(client_di, diario):
    r = client_di("csq").get("/api/v1/helpdesk/opzioni")
    assert r.status_code == 200
    assert [d["id"] for d in r.json()["diari"]] == [diario.pk]
    assert r.json()["staff"] is False
    assert {c["chiave"] for c in r.json()["categorie"]} >= {"tecnico", "altro"}
    assert client_di("segreteria").get("/api/v1/helpdesk/opzioni").json()["diari"] == []


def test_opzioni_capo_reparto(client_di, diario):
    r = client_di("crp").get("/api/v1/helpdesk/opzioni")
    assert r.status_code == 200
    assert [d["id"] for d in r.json()["diari"]] == [diario.pk]


# ── Azioni ──────────────────────────────────────────────────────────────────


def test_risposta_staff_prende_in_carico(client_di, utenti, ticket_csq):
    r = client_di("segreteria").post(
        f"/api/v1/helpdesk/{ticket_csq.pk}/risposte", **json_body({"testo": "Ci guardo"})
    )
    assert r.status_code == 201
    ticket_csq.refresh_from_db()
    assert ticket_csq.stato == StatoTicket.IN_LAVORAZIONE
    assert ticket_csq.assegnato_a == utenti["segreteria"]


def test_risposta_autore_e_vuota(client_di, ticket_csq):
    url = f"/api/v1/helpdesk/{ticket_csq.pk}/risposte"
    assert client_di("csq").post(url, **json_body({"testo": "Grazie"})).status_code == 201
    ticket_csq.refresh_from_db()
    assert ticket_csq.stato == StatoTicket.APERTO
    r = client_di("csq").post(url, **json_body({"testo": "   "}))
    assert r.status_code == 422 and "testo" in r.json()["errori"]
    assert client_di("estraneo").post(url, **json_body({"testo": "x"})).status_code == 403
    assert RispostaTicket.objects.count() == 1


def test_prendi_in_carico(client_di, utenti, ticket_csq):
    url = f"/api/v1/helpdesk/{ticket_csq.pk}/prendi-in-carico"
    assert client_di("csq").post(url).status_code == 403
    r = client_di("incaricato_eg").post(url)
    assert r.status_code == 200
    assert r.json()["stato"] == "in_lavorazione"
    assert r.json()["assegnato_a"]["email"] == utenti["incaricato_eg"].email


def test_chiudi(client_di, ticket_csq, ticket_crp):
    assert client_di("estraneo").post(f"/api/v1/helpdesk/{ticket_csq.pk}/chiudi").status_code == 403
    r = client_di("csq").post(f"/api/v1/helpdesk/{ticket_csq.pk}/chiudi")
    assert r.status_code == 200 and r.json()["stato"] == "chiuso"
    assert r.json()["chiuso_at"] is not None
    # ticket chiuso: niente più azioni
    assert client_di("csq").post(f"/api/v1/helpdesk/{ticket_csq.pk}/chiudi").status_code == 422
    assert client_di("admin").post(
        f"/api/v1/helpdesk/{ticket_csq.pk}/risposte", **json_body({"testo": "x"})
    ).status_code == 422
    # lo staff chiude anche i ticket altrui
    assert client_di("admin").post(f"/api/v1/helpdesk/{ticket_crp.pk}/chiudi").status_code == 200
