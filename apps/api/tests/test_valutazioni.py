"""API valutazione: dettaglio con visibilità per ruolo, assegnazione, proposte, pubblicazione."""
from __future__ import annotations

from unittest import mock

import pytest

from apps.api.tests.conftest import json_body
from apps.diaries.models import StatoDiario
from apps.evaluations.actions import assegna_pgv, proponi_pgv, valuta_direttamente
from apps.evaluations.models import StatoValutazione, Valutazione

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _senza_rate_limit():
    """Il rate limit API conta su Redis per IP (condiviso tra i test): qui non interessa."""
    with mock.patch("apps.siteconfig.middleware._rate_limit_check", return_value=(True, 0)):
        yield


@pytest.fixture
def inviato(diario):
    diario.stato = StatoDiario.INVIATO
    diario.save()
    return diario


def _url(diario, suffisso: str = "") -> str:
    return f"/api/v1/diari/{diario.pk}/valutazione{suffisso}"


# --- Dettaglio e visibilità ------------------------------------------------------

def test_dettaglio_staff_con_azioni(client_di, inviato, utenti):
    valuta_direttamente(inviato, "approvata", "Bene", utenti["incaricato_eg"])
    r = client_di("incaricato_eg").get(_url(inviato))
    assert r.status_code == 200
    dati = r.json()
    assert dati["esito"] == "approvata" and dati["stato"] == StatoValutazione.CONFERMATA
    assert dati["pubblicata"] is False and dati["diario_stato"] == StatoDiario.APPROVATO
    assert dati["azioni"]["puo_pubblicare"] is True
    seg = client_di("segreteria").get(_url(inviato)).json()["azioni"]
    assert seg["puo_pubblicare"] is False and seg["puo_assegnare_pgv"] is True


def test_dettaglio_senza_valutazione_404(client_di, inviato):
    assert client_di("admin").get(_url(inviato)).status_code == 404
    assert not Valutazione.objects.exists()  # la GET non crea nulla


def test_capo_squadriglia_mai(client_di, inviato, utenti):
    valuta_direttamente(inviato, "approvata", "", utenti["incaricato_eg"])
    from apps.evaluations.actions import pubblica_esito

    pubblica_esito(inviato, utenti["incaricato_eg"])
    assert client_di("csq").get(_url(inviato)).status_code == 403
    assert client_di("estraneo").get(_url(inviato)).status_code == 403


def test_capo_reparto_solo_dopo_pubblicazione(client_di, inviato, utenti):
    from apps.evaluations.actions import pubblica_esito

    valuta_direttamente(inviato, "non_approvata", "", utenti["incaricato_eg"])
    assert client_di("crp").get(_url(inviato)).status_code == 403
    pubblica_esito(inviato, utenti["incaricato_eg"])
    r = client_di("crp").get(_url(inviato))
    assert r.status_code == 200 and r.json()["esito"] == "non_approvata"


def test_capo_reparto_altrui_non_vede(client_di, inviato, utenti, org):
    from apps.accounts.models import Nomina, User
    from apps.evaluations.actions import pubblica_esito
    from apps.org.models import Socio

    valuta_direttamente(inviato, "approvata", "", utenti["incaricato_eg"])
    pubblica_esito(inviato, utenti["incaricato_eg"])
    socio = Socio.objects.create(codice_socio="700099", nome="Altro", cognome="Crp",
                                 categoria="capo", zona=org["zona"], gruppo=org["gruppo"])
    altro = User.objects.create_user(username="altrocrp@test.it", email="altrocrp@test.it",
                                     password="pw-test-123", ruolo="crp", socio=socio)
    Nomina.objects.get_or_create(utente=altro, ruolo="crp", defaults={"socio": socio})
    from django.test import Client

    c = Client()
    c.force_login(altro)
    assert c.get(_url(inviato)).status_code == 403


def test_pgv_solo_assegnati(client_di, inviato, utenti):
    valuta_direttamente(inviato, "approvata", "", utenti["incaricato_eg"])
    assert client_di("pgv").get(_url(inviato)).status_code == 403
    assegna_pgv(inviato, utenti["pgv"], utenti["incaricato_eg"])
    r = client_di("pgv").get(_url(inviato))
    assert r.status_code == 200 and r.json()["azioni"]["puo_proporre"] is True


def test_anonimo_401(client_di, inviato):
    assert client_di("anonimo").get(_url(inviato)).status_code == 401
    assert client_di("anonimo").post(_url(inviato, "/valuta"),
                                     **json_body({"esito": "approvata"})).status_code == 401


# --- Assegnazione e flusso Pattuglia GV --------------------------------------------

def test_assegna_pgv(client_di, inviato, utenti):
    body = json_body({"pgv_pk": utenti["pgv"].pk})
    assert client_di("crp").post(_url(inviato, "/assegna-pgv"), **body).status_code == 403
    assert client_di("pgv").post(_url(inviato, "/assegna-pgv"), **body).status_code == 403
    r = client_di("segreteria").post(_url(inviato, "/assegna-pgv"), **body)
    assert r.status_code == 200
    assert [a["pgv_pk"] for a in r.json()["assegnazioni"]] == [utenti["pgv"].pk]
    # Un utente che non è della Pattuglia GV non si può assegnare
    r = client_di("admin").post(_url(inviato, "/assegna-pgv"),
                                **json_body({"pgv_pk": utenti["crp"].pk}))
    assert r.status_code == 422
    assert client_di("admin").post(_url(inviato, "/assegna-pgv"),
                                   **json_body({"pgv_pk": 999999})).status_code == 404


def test_proposta_conferma(client_di, inviato, utenti):
    assegna_pgv(inviato, utenti["pgv"], utenti["incaricato_eg"])
    inviato.avvia_valutazione()
    r = client_di("pgv").post(_url(inviato, "/proposta"),
                              **json_body({"esito": "maggiori_info"}))
    assert r.status_code == 422  # la Pattuglia GV non propone "maggiori informazioni"
    r = client_di("pgv").post(_url(inviato, "/proposta"),
                              **json_body({"esito": "approvata", "note": "Ok"}))
    assert r.status_code == 200 and r.json()["stato"] == StatoValutazione.IN_REVISIONE
    assert r.json()["proposta_esito"] == "approvata"
    # Segreteria non conferma (come la vista web), l'Incaricato sì
    assert client_di("segreteria").post(_url(inviato, "/conferma"),
                                        **json_body({})).status_code == 403
    r = client_di("incaricato_eg").post(_url(inviato, "/conferma"), **json_body({"note": "Sì"}))
    assert r.status_code == 200 and r.json()["esito"] == "approvata"
    inviato.refresh_from_db()
    assert inviato.stato == StatoDiario.APPROVATO
    # Nessuna proposta più in revisione
    assert client_di("incaricato_eg").post(_url(inviato, "/rigetta")).status_code == 422


def test_rigetta_proposta(client_di, inviato, utenti):
    assegna_pgv(inviato, utenti["pgv"], utenti["incaricato_eg"])
    inviato.avvia_valutazione()
    proponi_pgv(inviato, "non_approvata", "", utenti["pgv"])
    assert client_di("pgv").post(_url(inviato, "/rigetta")).status_code == 403
    r = client_di("admin").post(_url(inviato, "/rigetta"))
    assert r.status_code == 200 and r.json()["stato"] == StatoValutazione.ASSEGNATA
    inviato.refresh_from_db()
    assert inviato.stato == StatoDiario.IN_VALUTAZIONE


def test_pgv_non_assegnato_non_propone(client_di, inviato, utenti):
    Valutazione.objects.create(diario=inviato)
    r = client_di("pgv").post(_url(inviato, "/proposta"), **json_body({"esito": "approvata"}))
    assert r.status_code == 403
    assert client_di("crp").post(_url(inviato, "/proposta"),
                                 **json_body({"esito": "approvata"})).status_code == 403


# --- Valutazione diretta, modifica, pubblicazione ----------------------------------

def test_valuta_modifica_pubblica(client_di, inviato, utenti):
    assert client_di("crp").post(_url(inviato, "/valuta"),
                                 **json_body({"esito": "approvata"})).status_code == 403
    r = client_di("segreteria").post(_url(inviato, "/valuta"),
                                     **json_body({"esito": "maggiori_info", "note": "Foto?"}))
    assert r.status_code == 200 and r.json()["diario_stato"] == StatoDiario.MAGGIORI_INFO
    assert client_di("admin").post(_url(inviato, "/valuta"),
                                   **json_body({"esito": "boh"})).status_code == 422

    assert client_di("segreteria").post(_url(inviato, "/modifica"),
                                        **json_body({"esito": "approvata"})).status_code == 403
    r = client_di("incaricato_eg").post(_url(inviato, "/modifica"),
                                        **json_body({"esito": "approvata"}))
    assert r.status_code == 200 and r.json()["esito"] == "approvata"

    assert client_di("segreteria").post(_url(inviato, "/pubblica")).status_code == 403
    r = client_di("incaricato_eg").post(_url(inviato, "/pubblica"))
    assert r.status_code == 200 and r.json()["stato"] == StatoDiario.APPROVATO
    inviato.refresh_from_db()
    assert inviato.pubblicato
    # Dopo la pubblicazione non si modifica più
    assert client_di("incaricato_eg").post(_url(inviato, "/modifica"),
                                           **json_body({"esito": "non_approvata"})).status_code == 422


def test_pubblica_senza_esito_422(client_di, inviato):
    Valutazione.objects.create(diario=inviato)
    assert client_di("admin").post(_url(inviato, "/pubblica")).status_code == 422


def test_valuta_stato_non_valutabile(client_di, diario):
    r = client_di("admin").post(_url(diario, "/valuta"), **json_body({"esito": "approvata"}))
    assert r.status_code == 422


# --- Transizioni FSM (endpoint esistente) -------------------------------------------

def test_azioni_fsm(client_di, diario):
    url = f"/api/v1/diari/{diario.pk}/azioni"
    assert client_di("estraneo").post(f"{url}/csq-invia").status_code == 403
    r = client_di("csq").post(f"{url}/csq-invia")
    assert r.status_code == 200 and r.json()["stato"] == StatoDiario.RELAZIONE_FINALE
    assert client_di("csq").post(f"{url}/csq-invia").status_code == 422
    assert client_di("crp").post(f"{url}/invia").json()["stato"] == StatoDiario.INVIATO
    assert client_di("crp").post(f"{url}/boh").status_code == 404


def test_rettifica_esito_prima_della_pubblicazione(client_di, inviato, utenti):
    """L'Incaricato modifica una decisione già presa (diario approvato → non approvato)."""
    valuta_direttamente(inviato, "approvata", "", utenti["incaricato_eg"])
    r = client_di("incaricato_eg").post(_url(inviato, "/modifica"),
                                        **json_body({"esito": "non_approvata", "note": "Rivisto"}))
    assert r.status_code == 200, r.content
    inviato.refresh_from_db()
    assert inviato.stato == StatoDiario.NON_APPROVATO
    assert r.json()["note"] == "Rivisto"
