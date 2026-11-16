"""API edizioni: home, CRUD, stato, dilazioni, pubblicazione esiti, Excel ed export diari."""
from __future__ import annotations

from unittest import mock

import pytest
from django.utils import timezone

from apps.api.tests.conftest import json_body
from apps.diaries.models import StatoDiario
from apps.editions.models import Dilazione, Edizione, StatoEdizione

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _senza_rate_limit():
    """Il rate limit API conta su Redis per IP (condiviso tra i test): qui non interessa."""
    with mock.patch("apps.siteconfig.middleware._rate_limit_check", return_value=(True, 0)):
        yield

STAFF = ("admin", "segreteria", "incaricato_eg")
NON_STAFF = ("pgv", "crp", "csq")


# --- Lettura ------------------------------------------------------------------

def test_lista_e_dettaglio_compatibili(client_di, edizione):
    c = client_di("csq")
    lista = c.get("/api/v1/edizioni").json()
    assert lista[0]["id"] == edizione.pk
    for campo in ("anno", "stato", "stato_display", "scadenza_evento", "scadenza_assemblea",
                  "data_evento_inizio", "data_evento_fine", "evento_comune"):
        assert campo in lista[0]
    r = c.get(f"/api/v1/edizioni/{edizione.pk}")
    assert r.status_code == 200 and r.json()["anno"] == 2098
    assert c.get("/api/v1/edizioni/999999").status_code == 404


def test_anonimo_401(client_di, edizione):
    c = client_di("anonimo")
    assert c.get("/api/v1/edizioni").status_code == 401
    assert c.get("/api/v1/edizioni/attiva").status_code == 401
    assert c.post("/api/v1/edizioni", **json_body({"anno": 2099})).status_code == 401


def test_attiva_staff_con_statistiche(client_di, edizione, diario):
    r = client_di("incaricato_eg").get("/api/v1/edizioni/attiva")
    assert r.status_code == 200
    dati = r.json()
    assert dati["puo_gestire"] is True
    rie = dati["riepilogo"]
    assert rie["edizione"]["id"] == edizione.pk
    assert rie["totale_diari"] == 1
    assert rie["stats_diari"]["totale"] == 1
    conteggi = {s["stato"]: s["totale"] for s in rie["stats_diari"]["per_stato"]}
    assert conteggi[StatoDiario.IN_COMPILAZIONE] == 1
    assert rie["filtri"]["zone"] == ["Zona API"]
    assert rie["puo_pubblicare_esiti"] is True
    seg = client_di("segreteria").get("/api/v1/edizioni/attiva").json()["riepilogo"]
    assert seg["puo_gestire"] is True and seg["puo_pubblicare_esiti"] is False


def test_attiva_per_ruolo_vede_solo_i_suoi_diari(client_di, edizione, diario):
    rie = client_di("crp").get("/api/v1/edizioni/attiva").json()["riepilogo"]
    assert rie["totale_diari"] == 1 and rie["stats_diari"] is None and rie["puo_gestire"] is False
    assert rie["puo_pubblicare_esiti"] is False
    assert client_di("estraneo").get("/api/v1/edizioni/attiva").json()["riepilogo"][
        "totale_diari"] == 0
    assert client_di("pgv").get(f"/api/v1/edizioni/{edizione.pk}/riepilogo").json()[
        "totale_diari"] == 0


def test_attiva_assente(client_di, edizione):
    Edizione.objects.update(stato=StatoEdizione.CHIUSA)
    dati = client_di("csq").get("/api/v1/edizioni/attiva").json()
    assert dati == {"riepilogo": None, "puo_gestire": False}


# --- CRUD ---------------------------------------------------------------------

@pytest.mark.parametrize("ruolo", STAFF)
def test_crea_edizione_staff(client_di, utenti, ruolo):
    r = client_di(ruolo).post("/api/v1/edizioni", **json_body({
        "anno": 2097, "scadenza_evento": "2097-05-01", "evento_comune": "Napoli",
    }))
    assert r.status_code == 201, r.content
    assert r.json()["stato"] == StatoEdizione.BOZZA
    assert Edizione.objects.filter(anno=2097, evento_comune="Napoli").exists()


@pytest.mark.parametrize("ruolo", NON_STAFF)
def test_crea_edizione_non_staff_403(client_di, utenti, ruolo):
    r = client_di(ruolo).post("/api/v1/edizioni", **json_body({"anno": 2097}))
    assert r.status_code == 403
    assert not Edizione.objects.filter(anno=2097).exists()


def test_crea_edizione_validazione(client_di, edizione):
    c = client_di("admin")
    r = c.post("/api/v1/edizioni", **json_body({"anno": 2098}))  # anno già usato
    assert r.status_code == 422 and "anno" in r.json()["errori"]
    r = c.post("/api/v1/edizioni", **json_body({
        "anno": 2096, "data_evento_inizio": "2096-05-10", "data_evento_fine": "2096-05-01",
    }))
    assert r.status_code == 422 and "data_evento_fine" in r.json()["errori"]


def test_modifica_parziale(client_di, edizione):
    r = client_di("segreteria").patch(
        f"/api/v1/edizioni/{edizione.pk}", **json_body({"evento_localita": "Base scout"})
    )
    assert r.status_code == 200, r.content
    edizione.refresh_from_db()
    assert edizione.evento_localita == "Base scout"
    assert edizione.anno == 2098 and edizione.stato == StatoEdizione.APERTA
    assert client_di("crp").patch(
        f"/api/v1/edizioni/{edizione.pk}", **json_body({"anno": 1})
    ).status_code == 403


# --- Stato --------------------------------------------------------------------

def test_transizioni_stato(client_di, utenti):
    ed = Edizione.objects.create(anno=2095)
    c = client_di("incaricato_eg")
    url = f"/api/v1/edizioni/{ed.pk}/azioni"
    assert c.post(f"{url}/chiudi").status_code == 422  # da bozza non si chiude
    assert c.post(f"{url}/apri").json()["stato"] == StatoEdizione.APERTA
    assert c.post(f"{url}/avvia-valutazione").json()["stato"] == StatoEdizione.IN_VALUTAZIONE
    assert c.post(f"{url}/chiudi").json()["stato"] == StatoEdizione.CHIUSA
    assert c.post(f"{url}/boh").status_code == 404
    assert client_di("crp").post(f"{url}/apri").status_code == 403


# --- Dilazioni ----------------------------------------------------------------

def test_dilazione_crea_e_elenca(client_di, edizione, diario, utenti):
    c = client_di("segreteria")
    nuova = (timezone.now().date() + timezone.timedelta(days=90)).isoformat()
    r = c.post(f"/api/v1/edizioni/{edizione.pk}/dilazioni", **json_body({
        "diario_id": diario.pk, "nuova_scadenza": nuova, "motivazione": "Malattia",
    }))
    assert r.status_code == 201, r.content
    d = Dilazione.objects.get()
    assert d.concessa_da == utenti["segreteria"]
    diario.refresh_from_db()
    assert diario.scadenza_effettiva().isoformat() == nuova
    lista = c.get(f"/api/v1/edizioni/{edizione.pk}/dilazioni").json()
    assert lista["count"] == 1 and lista["items"][0]["squadriglia"] == "Tigri"
    assert client_di("crp").get(f"/api/v1/edizioni/{edizione.pk}/dilazioni").status_code == 403


def test_dilazione_regole(client_di, edizione, diario):
    c = client_di("admin")
    url = f"/api/v1/edizioni/{edizione.pk}/dilazioni"
    assert c.post(url, **json_body({"diario_id": diario.pk, "nuova_scadenza": "2099-01-01",
                                    "motivazione": ""})).status_code == 422
    assert client_di("crp").post(url, **json_body({
        "diario_id": diario.pk, "nuova_scadenza": "2099-01-01", "motivazione": "x",
    })).status_code == 403
    altra = Edizione.objects.create(anno=2094)
    assert c.post(f"/api/v1/edizioni/{altra.pk}/dilazioni", **json_body({
        "diario_id": diario.pk, "nuova_scadenza": "2099-01-01", "motivazione": "x",
    })).status_code == 404
    diario.stato = StatoDiario.INVIATO
    diario.save()
    r = c.post(url, **json_body({"diario_id": diario.pk, "nuova_scadenza": "2099-01-01",
                                  "motivazione": "x"}))
    assert r.status_code == 422
    assert not Dilazione.objects.exists()


# --- Esiti ----------------------------------------------------------------------

def _diario_valutato(diario, utenti):
    from apps.evaluations.actions import valuta_direttamente

    diario.stato = StatoDiario.INVIATO
    diario.save()
    valuta_direttamente(diario, "approvata", "", utenti["incaricato_eg"])


def test_pubblica_esiti_edizione(client_di, edizione, diario, utenti):
    _diario_valutato(diario, utenti)
    url = f"/api/v1/edizioni/{edizione.pk}/pubblica-esiti"
    assert client_di("segreteria").post(url).status_code == 403  # come la vista web
    assert client_di("crp").post(url).status_code == 403
    assert client_di("admin").post(f"{url}?scadenza=boh").status_code == 422
    r = client_di("incaricato_eg").post(f"{url}?scadenza=prima")
    assert r.status_code == 200 and r.json() == {"pubblicati": 1}
    diario.refresh_from_db()
    assert diario.pubblicato
    assert client_di("incaricato_eg").post(url).json() == {"pubblicati": 0}


def test_esiti_excel(client_di, edizione, diario):
    r = client_di("incaricato_eg").get(f"/api/v1/edizioni/{edizione.pk}/esiti-excel")
    assert r.status_code == 200
    assert r["Content-Disposition"] == 'attachment; filename="Esiti_GV_2098.xlsx"'
    assert r.content[:2] == b"PK"
    assert client_di("crp").get(f"/api/v1/edizioni/{edizione.pk}/esiti-excel").status_code == 403


# --- Export diari -----------------------------------------------------------------

@pytest.mark.parametrize("formato", ["xlsx", "ods", "csv"])
def test_export_diari_sincrono(client_di, edizione, diario, formato):
    r = client_di("admin").get(f"/api/v1/edizioni/{edizione.pk}/export-diari?formato={formato}")
    assert r.status_code == 200
    assert r["Content-Disposition"] == f'attachment; filename="Export_diari_2098.{formato}"'


def test_export_diari_asincrono(client_di, edizione, diario, utenti, settings):
    settings.EXPORT_DIARI_SOGLIA_ASYNC = 0
    with mock.patch("apps.exports.tasks.task_export_diari.delay") as delay:
        r = client_di("segreteria").get(f"/api/v1/edizioni/{edizione.pk}/export-diari?formato=ods")
        assert r.status_code == 202
        assert r.json()["diari"] == 1 and r.json()["formato"] == "ods"
        delay.assert_called_once_with(edizione.pk, utenti["segreteria"].pk, "ods")
        # Il CSV resta sincrono
        r = client_di("segreteria").get(f"/api/v1/edizioni/{edizione.pk}/export-diari?formato=csv")
        assert r.status_code == 200
        assert delay.call_count == 1


def test_export_diari_non_staff(client_di, edizione):
    assert client_di("crp").get(f"/api/v1/edizioni/{edizione.pk}/export-diari").status_code == 403
    assert client_di("anonimo").get(
        f"/api/v1/edizioni/{edizione.pk}/export-diari").status_code == 401


# --- Viste web (rifattorizzate sui servizi) -----------------------------------------

def test_vista_web_cambio_stato_e_dilazione(client_di, edizione, diario, settings):
    settings.SKIP_MFA_ENFORCEMENT = True
    c = client_di("incaricato_eg")
    r = c.post(f"/edizioni/{edizione.pk}/stato/avvia_valutazione/")
    assert r.status_code == 302
    edizione.refresh_from_db()
    assert edizione.stato == StatoEdizione.IN_VALUTAZIONE
    r = c.post(f"/edizioni/dilazione/{diario.pk}/",
               {"nuova_scadenza": "2099-02-01", "motivazione": "Motivo"})
    assert r.status_code == 302 and Dilazione.objects.count() == 1
    assert client_di("crp").post(f"/edizioni/{edizione.pk}/stato/chiudi/").status_code == 403
