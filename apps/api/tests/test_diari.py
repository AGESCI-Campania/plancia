"""API `/api/v1/diari`: lista e filtri, dettaglio e permessi, moduli 1–6, allegati, PDF, referenti.

Riprende i casi dei test delle viste web (`apps/diaries/tests/`) e degli endpoint PWA
(`apps/diaries/tests/test_api.py`) sulle regole condivise.
"""
from __future__ import annotations

import io
import uuid
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.api.tests.conftest import json_body
from apps.diaries.models import (
    Allegato,
    Anagrafica,
    Diario,
    Impresa,
    Missione,
    PostoAzioneMissione,
    RelazioneFinale,
    StatoDiario,
    TipoDiario,
)

pytestmark = pytest.mark.django_db

STAFF = ("admin", "segreteria", "incaricato_eg")


@pytest.fixture(autouse=True)
def _cache_e_media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    cache.clear()
    yield
    cache.clear()


def _url(diario, suffisso: str = "") -> str:
    return f"/api/v1/diari/{diario.pk}{suffisso}"


def _stato(diario, stato) -> None:
    diario.stato = stato
    diario.save(update_fields=["stato"])


def _socio(org, codice: str, categoria: str, nome: str, **extra):
    from apps.org.models import Socio

    return Socio.objects.create(
        codice_socio=codice, nome=nome, cognome="Nuovo", email=f"{codice}@test.it",
        categoria=categoria, zona=org["zona"], gruppo=org["gruppo"], **extra,
    )


def _assegna_pgv(diario, pgv) -> None:
    from apps.evaluations.models import AssegnazionePGV, Valutazione

    val, _ = Valutazione.objects.get_or_create(diario=diario)
    AssegnazionePGV.objects.create(valutazione=val, pgv=pgv)


def _png(lato: int = 2000) -> SimpleUploadedFile:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (lato, lato // 2), "green").save(buf, format="PNG")
    return SimpleUploadedFile("foto.png", buf.getvalue(), content_type="image/png")


ANAGRAFICA = {
    "squadriglia_nome": "Pantere", "tipo_diario": "nuovo",
    "crp_nome": "Mario", "crp_cognome": "Rossi", "crp_email": "m@test.it", "crp_cell": "1",
    "csq_nome": "Luigi", "csq_cognome": "Bianchi", "csq_email": "l@test.it", "csq_cell": "2",
    "specialita": "Campismo", "partecipa_evento": True,
}
RELAZIONE = {
    "sintesi_impresa_1": "a", "sintesi_impresa_2": "b", "sintesi_missione": "c",
    "considerazioni": "d", "specialita_conquistata": True,
}


# ---------------------------------------------------------------------------
# Lista
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ruolo,vede", [
    ("admin", True), ("segreteria", True), ("incaricato_eg", True), ("crp", True),
    ("csq", True), ("estraneo", False), ("pgv", False),
])
def test_lista_visibilita_per_ruolo(client_di, diario, ruolo, vede):
    r = client_di(ruolo).get("/api/v1/diari")
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()["items"]]
    assert (diario.pk in ids) is vede


def test_lista_anonimo_401(client_di, diario):
    assert client_di("anonimo").get("/api/v1/diari").status_code == 401


def test_lista_pgv_assegnato(client_di, diario, utenti):
    _assegna_pgv(diario, utenti["pgv"])
    r = client_di("pgv").get("/api/v1/diari")
    assert [d["id"] for d in r.json()["items"]] == [diario.pk]


def test_lista_campi_tabella(client_di, diario, utenti):
    Anagrafica.objects.create(diario=diario, specialita="Natura")
    riga = client_di("admin").get("/api/v1/diari").json()["items"][0]
    assert riga["squadriglia"] == "Tigri"
    assert riga["specialita"] == "Natura"
    assert riga["csq"]["id"] == utenti["csq"].socio.pk
    assert riga["crp"]["nome"] == "Crp"
    assert riga["zona_id"] == diario.squadriglia.reparto.gruppo.zona_id
    assert riga["puo_pdf"] is False  # in compilazione
    assert riga["stato_display"] == "In compilazione"


@pytest.fixture
def due_diari(diario, org, edizione, utenti):
    """Secondo diario (Aquile, rinnovo, inviato) in un'altra zona/gruppo/reparto."""
    from apps.org.models import Gruppo, Reparto, Squadriglia, Zona

    zona = Zona.objects.create(nome="Zona Bis")
    gruppo = Gruppo.objects.create(nome="Gruppo Bis", zona=zona)
    reparto = Reparto.objects.create(nome="Reparto Bis", gruppo=gruppo)
    sq = Squadriglia.objects.create(nome="Aquile", reparto=reparto)
    altro = Diario.objects.create(
        edizione=edizione, squadriglia=sq, tipo=TipoDiario.RINNOVO, stato=StatoDiario.INVIATO,
        crp=_socio(org, "710001", "capo", "Zeta"),
    )
    Anagrafica.objects.create(diario=altro, specialita="Nautica")
    return diario, altro


@pytest.mark.parametrize("parametri,attesi", [
    ("tipo=rinnovo", ["Aquile"]),
    ("stato=inviato", ["Aquile"]),
    ("stato=inviato,in_compilazione", ["Aquile", "Tigri"]),
    ("specialita=Nautica", ["Aquile"]),
    ("q=zeta", ["Aquile"]),
    ("q=csq test", ["Tigri"]),
    ("q=tigr", ["Tigri"]),
    ("ordina=-squadriglia", ["Tigri", "Aquile"]),
    ("ordina=squadriglia", ["Aquile", "Tigri"]),
])
def test_lista_filtri(client_di, due_diari, parametri, attesi):
    r = client_di("segreteria").get(f"/api/v1/diari?{parametri}")
    assert r.status_code == 200
    nomi = [d["squadriglia"] for d in r.json()["items"]]
    if not parametri.startswith("ordina"):
        nomi.sort()
    assert nomi == attesi


def test_lista_filtri_per_id_e_edizione(client_di, due_diari, edizione):
    tigri, aquile = due_diari
    c = client_di("admin")
    rep = aquile.squadriglia.reparto
    for parametro, valore in (("zona_id", rep.gruppo.zona_id), ("gruppo_id", rep.gruppo_id),
                              ("reparto_id", rep.pk)):
        r = c.get(f"/api/v1/diari?{parametro}={valore}")
        assert [d["id"] for d in r.json()["items"]] == [aquile.pk]
    assert c.get(f"/api/v1/diari?edizione_id={edizione.pk}").json()["count"] == 2
    assert c.get("/api/v1/diari?edizione_id=999999").json()["count"] == 0


def test_lista_paginata_e_ordinamento_non_valido(client_di, due_diari):
    c = client_di("admin")
    r = c.get("/api/v1/diari?limit=1&ordina=squadriglia")
    assert r.json()["count"] == 2 and len(r.json()["items"]) == 1
    assert c.get("/api/v1/diari?ordina=password").status_code == 422


def test_filtri_disponibili(client_di, due_diari):
    r = client_di("admin").get("/api/v1/diari/filtri")
    assert r.status_code == 200
    body = r.json()
    assert {z["nome"] for z in body["zone"]} == {"Zona API", "Zona Bis"}
    assert body["specialita"] == ["Nautica"]
    assert {"valore": "inviato", "etichetta": "Inviato"} in body["stati"]
    assert "squadriglia" in body["ordinamenti"]


def test_filtri_solo_sui_diari_visibili(client_di, due_diari):
    body = client_di("csq").get("/api/v1/diari/filtri").json()
    assert [z["nome"] for z in body["zone"]] == ["Zona API"]
    assert body["specialita"] == []
    assert client_di("anonimo").get("/api/v1/diari/filtri").status_code == 401


# ---------------------------------------------------------------------------
# Dettaglio e permessi calcolati
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ruolo,atteso", [
    ("admin", 200), ("segreteria", 200), ("incaricato_eg", 200), ("crp", 200), ("csq", 200),
    ("estraneo", 403), ("pgv", 403),
])
def test_dettaglio_per_ruolo(client_di, diario, ruolo, atteso):
    assert client_di(ruolo).get(_url(diario)).status_code == atteso


def test_dettaglio_anonimo_e_inesistente(client_di, diario):
    assert client_di("anonimo").get(_url(diario)).status_code == 401
    assert client_di("admin").get("/api/v1/diari/999999").status_code == 404


def test_dettaglio_permessi_csq(client_di, diario):
    RelazioneFinale.objects.create(diario=diario, considerazioni="segreto")
    body = client_di("csq").get(_url(diario)).json()
    p = body["permessi"]
    assert p["puo_modificare_moduli"] is True
    assert p["puo_vedere_relazione"] is False
    assert p["puo_cambiare_csq"] is False and p["puo_cambiare_crp"] is False
    assert p["puo_pdf"] is False and p["puo_caricare_allegati"] is True
    assert body["relazione_finale"] is None
    assert body["stato_moduli"]["relazione_finale"] is None
    assert "relazione_finale" not in body["stato_moduli"]["versioni"]


def test_dettaglio_permessi_crp(client_di, diario):
    p = client_di("crp").get(_url(diario)).json()["permessi"]
    assert p["puo_modificare_moduli"] is False
    assert p["puo_vedere_relazione"] is True
    assert p["puo_modificare_relazione"] is False  # solo in RELAZIONE_FINALE
    assert p["puo_cambiare_csq"] is True
    assert p["puo_cambiare_crp"] is False
    _stato(diario, StatoDiario.RELAZIONE_FINALE)
    p = client_di("crp").get(_url(diario)).json()["permessi"]
    assert p["puo_modificare_relazione"] is True and p["puo_inviare"] is True
    assert p["puo_cambiare_csq"] is False and p["puo_eliminare_allegati"] is True


def test_dettaglio_permessi_staff(client_di, diario):
    body = client_di("segreteria").get(_url(diario)).json()
    p = body["permessi"]
    assert p["puo_cambiare_csq"] and p["puo_cambiare_crp"] and p["puo_concedere_dilazione"]
    assert p["puo_riaprire"] is False
    assert body["scadenze"]["riferimento"] == "prima"
    assert body["scadenze"]["effettiva"] == str(diario.edizione.scadenza_evento)
    _stato(diario, StatoDiario.INVIATO)
    p = client_di("segreteria").get(_url(diario)).json()["permessi"]
    assert p["puo_pdf"] is True
    assert p["puo_cambiare_csq"] is False and p["puo_concedere_dilazione"] is False


def test_dettaglio_permessi_inviare_csq_richiede_moduli_completi(client_di, diario):
    assert client_di("csq").get(_url(diario)).json()["permessi"]["puo_inviare_csq"] is False
    diario.tipo = TipoDiario.RINNOVO
    diario.save()
    from apps.diaries.models import Presentazione

    Anagrafica.objects.create(diario=diario)
    Presentazione.objects.create(diario=diario)
    Impresa.objects.create(diario=diario, numero=1)
    body = client_di("csq").get(_url(diario)).json()
    assert body["permessi"]["puo_inviare_csq"] is True
    assert body["stato_moduli"]["moduli_csq_completi"] is True
    assert body["stato_moduli"]["impresa_2_obbligatoria"] is False


def test_dettaglio_valutazione_solo_se_pubblicata(client_di, diario, utenti):
    from apps.evaluations.models import Valutazione

    val = Valutazione.objects.create(diario=diario, note="riservate")
    assert client_di("crp").get(_url(diario)).json()["valutazione"] is None
    assert client_di("csq").get(_url(diario)).json()["valutazione"] is None
    assert client_di("incaricato_eg").get(_url(diario)).json()["valutazione"] is not None
    assert val.pk


def test_dettaglio_pgv_assegnato(client_di, diario, utenti):
    _assegna_pgv(diario, utenti["pgv"])
    r = client_di("pgv").get(_url(diario))
    assert r.status_code == 200
    assert r.json()["permessi"]["puo_modificare_moduli"] is False


def test_stato_leggero_e_permessi(client_di, diario):
    r = client_di("csq").get(_url(diario, "/stato"))
    assert r.status_code == 200
    assert r.json()["puo_editare"] is True and r.json()["versioni"]["anagrafica"] == 0
    assert client_di("estraneo").get(_url(diario, "/stato")).status_code == 403
    assert client_di("crp").get(_url(diario, "/permessi")).json()["puo_cambiare_csq"] is True
    assert client_di("anonimo").get(_url(diario, "/permessi")).status_code == 401


# ---------------------------------------------------------------------------
# Moduli 1–5: GET + PUT versionato
# ---------------------------------------------------------------------------

def test_anagrafica_get_vuota_e_put(client_di, diario):
    c = client_di("csq")
    r = c.get(_url(diario, "/anagrafica"))
    assert r.status_code == 200 and r.json()["version"] == 0
    r = c.put(_url(diario, "/anagrafica"), **json_body({"version": 0, "data": ANAGRAFICA}))
    assert r.status_code == 200 and r.json()["version"] == 1
    diario.refresh_from_db()
    assert diario.squadriglia.nome == "Pantere"
    assert c.get(_url(diario, "/anagrafica")).json()["data"]["squadriglia_nome"] == "Pantere"
    # Le email dei referenti le cambia solo lo staff
    assert Anagrafica.objects.get(diario=diario).csq_email == ""


def test_anagrafica_conflitto_409(client_di, diario):
    Anagrafica.objects.create(diario=diario, version=3)
    r = client_di("csq").put(_url(diario, "/anagrafica"), **json_body({"version": 2, "data": ANAGRAFICA}))
    assert r.status_code == 409 and r.json() == {"error": "conflict", "server_version": 3}


def test_put_modulo_transita_non_iniziato(client_di, diario):
    _stato(diario, StatoDiario.NON_INIZIATO)
    r = client_di("csq").put(_url(diario, "/missione"), **json_body({"version": 0, "data": {}}))
    assert r.status_code == 200
    diario.refresh_from_db()
    assert diario.stato == StatoDiario.IN_COMPILAZIONE


@pytest.mark.parametrize("ruolo,atteso", [
    ("csq", 200), ("admin", 200), ("crp", 403), ("estraneo", 403), ("pgv", 403), ("anonimo", 401),
])
def test_put_modulo_permessi(client_di, diario, ruolo, atteso):
    r = client_di(ruolo).put(_url(diario, "/presentazione"),
                             **json_body({"version": 0, "data": {"membri": []}}))
    assert r.status_code == atteso


def test_put_modulo_csq_dopo_invio_403(client_di, diario):
    _stato(diario, StatoDiario.INVIATO)
    r = client_di("csq").put(_url(diario, "/imprese/1"), **json_body({"version": 0, "data": {}}))
    assert r.status_code == 403


def test_get_moduli_visibili_e_non(client_di, diario):
    for suffisso in ("/anagrafica", "/presentazione", "/imprese/1", "/imprese/2", "/missione"):
        assert client_di("crp").get(_url(diario, suffisso)).status_code == 200
        assert client_di("estraneo").get(_url(diario, suffisso)).status_code == 403
    assert client_di("crp").get(_url(diario, "/imprese/3")).status_code == 404


def test_put_idempotente_con_chiave(client_di, diario):
    c = client_di("csq")
    chiave = str(uuid.uuid4())
    corpo = json_body({"version": 0, "data": {"cosa_sappiamo_fare": "nodi", "membri": []}})
    r1 = c.put(_url(diario, "/presentazione"), HTTP_IDEMPOTENCY_KEY=chiave, **corpo)
    r2 = c.put(_url(diario, "/presentazione"), HTTP_IDEMPOTENCY_KEY=chiave, **corpo)
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json() and r2.json()["version"] == 1
    # Senza chiave lo stesso invio è un conflitto
    assert c.put(_url(diario, "/presentazione"), **corpo).status_code == 409


def test_impresa_get_e_put_con_posti_e_specialita(client_di, diario):
    c = client_di("csq")
    data = {
        "titolo": "Ponte", "posti_azione": [{"chi": "Anna", "cosa": "Foto"}],
        "specialita": [{"chi": "Anna", "nome": "Fotografo", "stato": "conquistata"}],
        "brevetti": [{"chi": "Bea", "nome": "Pioniere", "stato": "in_cammino"}],
    }
    r = c.put(_url(diario, "/imprese/2"), **json_body({"version": 0, "data": data}))
    assert r.status_code == 200
    body = c.get(_url(diario, "/imprese/2")).json()
    assert body["version"] == 1 and body["data"]["numero"] == 2
    assert body["data"]["posti_azione"][0]["chi"] == "Anna"
    assert body["data"]["specialita"][0]["tipo"] == "specialita"
    assert body["data"]["brevetti"][0]["nome"] == "Pioniere"


def test_missione_posti_azione_sync(client_di, diario):
    m = Missione.objects.create(diario=diario, version=1)
    p = PostoAzioneMissione.objects.create(missione=m, descrizione="Vecchio")
    c = client_di("csq")
    # Senza posti_azione nel corpo i posti non cambiano
    r = c.put(_url(diario, "/missione"), **json_body({"version": 1, "data": {"titolo": "Faro"}}))
    assert r.status_code == 200 and [x["descrizione"] for x in r.json()["data"]["posti_azione"]] == ["Vecchio"]
    data = {"titolo": "Faro", "posti_azione": [{"id": p.pk, "descrizione": "Aggiornato"},
                                              {"descrizione": "Nuovo"}]}
    r = c.put(_url(diario, "/missione"), **json_body({"version": 2, "data": data}))
    assert sorted(x["descrizione"] for x in r.json()["data"]["posti_azione"]) == ["Aggiornato", "Nuovo"]
    r = c.put(_url(diario, "/missione"),
              **json_body({"version": 3, "data": {"posti_azione": [{"descrizione": ""}]}}))
    assert r.status_code == 400


def test_salvataggio_incrementa_version(client_di, diario):
    """Un salvataggio da un altro dispositivo invalida la versione in mano alla SPA (409)."""
    Missione.objects.create(diario=diario)
    c = client_di("csq")
    r = c.put(_url(diario, "/missione"), **json_body({"version": 0, "data": {"titolo": "Altro"}}))
    assert r.status_code == 200
    r = c.put(_url(diario, "/missione"), **json_body({"version": 0, "data": {}}))
    assert r.status_code == 409 and r.json()["server_version"] == 1


# ---------------------------------------------------------------------------
# Modulo 6 — Relazione finale
# ---------------------------------------------------------------------------

def test_relazione_mai_al_csq(client_di, diario):
    RelazioneFinale.objects.create(diario=diario)
    assert client_di("csq").get(_url(diario, "/relazione-finale")).status_code == 403
    _stato(diario, StatoDiario.RELAZIONE_FINALE)
    r = client_di("csq").put(_url(diario, "/relazione-finale"), **json_body({"data": RELAZIONE}))
    assert r.status_code == 403


def test_relazione_crp_solo_in_relazione_finale(client_di, diario):
    c = client_di("crp")
    r = c.get(_url(diario, "/relazione-finale"))
    assert r.status_code == 200 and r.json()["version"] == 0
    r = c.put(_url(diario, "/relazione-finale"), **json_body({"version": 0, "data": RELAZIONE}))
    assert r.status_code == 422
    _stato(diario, StatoDiario.RELAZIONE_FINALE)
    r = c.put(_url(diario, "/relazione-finale"), **json_body({"version": 0, "data": RELAZIONE}))
    assert r.status_code == 200 and r.json()["version"] == 1
    r = c.put(_url(diario, "/relazione-finale"), **json_body({"version": 0, "data": RELAZIONE}))
    assert r.status_code == 409 and r.json()["server_version"] == 1
    # Compatibilità app mobile: senza version nessun controllo
    r = c.put(_url(diario, "/relazione-finale"),
              **json_body({"data": {**RELAZIONE, "specialita_conquistata": None}}))
    assert r.status_code == 200 and r.json()["data"]["specialita_conquistata"] is None
    assert client_di("crp").get(_url(diario)).json()["relazione_finale"]["sintesi_impresa_1"] == "a"


def test_relazione_staff_e_estraneo(client_di, diario):
    r = client_di("admin").put(_url(diario, "/relazione-finale"), **json_body({"data": RELAZIONE}))
    assert r.status_code == 200
    assert client_di("estraneo").get(_url(diario, "/relazione-finale")).status_code == 403


# ---------------------------------------------------------------------------
# Allegati
# ---------------------------------------------------------------------------

def _carica(c, diario, modulo="impresa_1", file=None, **extra):
    return c.post(_url(diario, "/allegati"), {"modulo": modulo, "file": file or _png()}, **extra)


def test_upload_ridimensiona_e_inizia(client_di, diario):
    from PIL import Image

    _stato(diario, StatoDiario.NON_INIZIATO)
    r = _carica(client_di("csq"), diario)
    assert r.status_code == 201
    body = r.json()
    assert body["mime"] == "image/jpeg" and body["nome"] == "foto.jpg"
    assert body["stato_sync"] == "locale"
    allegato = Allegato.objects.get(pk=body["id"])
    with allegato.file.open("rb") as f:
        assert max(Image.open(f).size) == 1024  # Impostazioni.allegati_max_px di default
    diario.refresh_from_db()
    assert diario.stato == StatoDiario.IN_COMPILAZIONE


def test_upload_con_drive_accoda_task(client_di, diario):
    diario.edizione.drive_oauth_account = "drive@test.it"
    diario.edizione.save()
    from apps.storage_drive import tasks

    with mock.patch.object(tasks.task_carica_allegato_drive, "delay") as delay:
        r = _carica(client_di("csq"), diario)
    assert r.status_code == 201 and r.json()["stato_sync"] == "in_coda"
    delay.assert_called_once_with(r.json()["id"])


@pytest.mark.parametrize("ruolo,atteso", [
    ("csq", 201), ("segreteria", 201), ("crp", 403), ("estraneo", 403), ("pgv", 403), ("anonimo", 401),
])
def test_upload_permessi(client_di, diario, ruolo, atteso):
    assert _carica(client_di(ruolo), diario).status_code == atteso


def test_upload_validazione(client_di, diario):
    c = client_di("csq")
    r = _carica(c, diario, modulo="anagrafica")
    assert r.status_code == 422 and "modulo" in r.json()["errori"]
    pdf = SimpleUploadedFile("x.pdf", b"%PDF", content_type="application/pdf")
    r = _carica(c, diario, file=pdf)
    assert r.status_code == 422 and "file" in r.json()["errori"]


def test_upload_idempotente(client_di, diario):
    c = client_di("csq")
    chiave = str(uuid.uuid4())
    r1 = _carica(c, diario, HTTP_IDEMPOTENCY_KEY=chiave)
    r2 = _carica(c, diario, HTTP_IDEMPOTENCY_KEY=chiave)
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert Allegato.objects.filter(diario=diario).count() == 1


def test_elenco_anteprima_miniatura_download(client_di, diario):
    from PIL import Image

    _carica(client_di("csq"), diario, modulo="missione")
    c = client_di("crp")
    elenco = c.get(_url(diario, "/allegati?modulo=missione")).json()
    assert len(elenco) == 1
    assert c.get(_url(diario, "/allegati?modulo=impresa_1")).json() == []
    a = elenco[0]
    r = c.get(a["anteprima_url"])
    assert r.status_code == 200 and r["Content-Type"] == "image/jpeg"
    r = c.get(a["miniatura_url"])
    assert r.status_code == 200 and max(Image.open(io.BytesIO(r.content)).size) == 320
    r = c.get(a["download_url"])
    assert r.status_code == 200 and r["Content-Disposition"].startswith("attachment")
    assert client_di("estraneo").get(a["anteprima_url"]).status_code == 403
    assert c.get(_url(diario, "/allegati/999999/anteprima")).status_code == 404


def test_allegato_di_altro_diario_404(client_di, diario, org, edizione):
    _carica(client_di("csq"), diario)
    allegato = Allegato.objects.get(diario=diario)
    altro = Diario.objects.create(edizione=edizione, squadriglia=org["squadriglia_altra"])
    r = client_di("admin").get(f"/api/v1/diari/{altro.pk}/allegati/{allegato.pk}/file")
    assert r.status_code == 404
    r = client_di("admin").delete(f"/api/v1/diari/{altro.pk}/allegati/{allegato.pk}")
    assert r.status_code == 404 and Allegato.objects.filter(pk=allegato.pk).exists()


def test_elimina_allegato(client_di, diario):
    _carica(client_di("csq"), diario)
    allegato = Allegato.objects.get(diario=diario)
    assert client_di("crp").delete(_url(diario, f"/allegati/{allegato.pk}")).status_code == 403
    assert client_di("csq").delete(_url(diario, f"/allegati/{allegato.pk}")).status_code == 204
    assert not Allegato.objects.filter(pk=allegato.pk).exists()
    assert client_di("csq").delete(_url(diario, f"/allegati/{allegato.pk}")).status_code == 404


def test_elimina_allegato_per_stato(client_di, diario):
    _carica(client_di("csq"), diario)
    allegato = Allegato.objects.get(diario=diario)
    _stato(diario, StatoDiario.INVIATO)
    assert client_di("csq").delete(_url(diario, f"/allegati/{allegato.pk}")).status_code == 403
    assert client_di("crp").delete(_url(diario, f"/allegati/{allegato.pk}")).status_code == 403
    _stato(diario, StatoDiario.RELAZIONE_FINALE)
    assert client_di("crp").delete(_url(diario, f"/allegati/{allegato.pk}")).status_code == 204


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def test_pdf_mai_al_csq_e_solo_dopo_invio(client_di, diario):
    assert client_di("csq").get(_url(diario, "/pdf/stato")).status_code == 403
    assert client_di("crp").get(_url(diario, "/pdf/stato")).status_code == 422
    assert client_di("estraneo").post(_url(diario, "/pdf")).status_code == 403
    assert client_di("anonimo").get(_url(diario, "/pdf")).status_code == 401
    _stato(diario, StatoDiario.INVIATO)
    assert client_di("csq").get(_url(diario, "/pdf")).status_code == 403


def test_pdf_senza_drive_generato_al_volo(client_di, diario):
    _stato(diario, StatoDiario.INVIATO)
    c = client_di("crp")
    body = c.get(_url(diario, "/pdf/stato")).json()
    assert body["stato"] == "pronto" and body["sincrono"] is True
    assert body["download_url"] == _url(diario, "/pdf")
    with mock.patch("apps.exports.service.genera_pdf_diario", return_value=b"%PDF-1.4 test") as gen:
        r = c.get(_url(diario, "/pdf"))
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert r.content == b"%PDF-1.4 test" and "Diario_Tigri_2098.pdf" in r["Content-Disposition"]
    gen.assert_called_once()
    assert gen.call_args.kwargs == {"include_relazione": True}


@pytest.fixture
def diario_drive(diario):
    diario.edizione.drive_oauth_account = "drive@test.it"
    diario.edizione.save()
    _stato(diario, StatoDiario.INVIATO)
    return diario


def test_pdf_con_drive_avvio_e_lock(client_di, diario_drive):
    from apps.exports import tasks

    d = diario_drive
    c = client_di("incaricato_eg")
    assert c.get(_url(d, "/pdf/stato")).json()["stato"] == "da_generare"
    with mock.patch.object(tasks.task_genera_pdf_diario, "delay") as delay, \
            mock.patch("apps.exports.tasks._invia_mail_pdf") as mail:
        r = c.post(_url(d, "/pdf"))
        assert r.status_code == 202
        assert r.json()["stato"] == "in_generazione" and r.json()["avviato"] is True
        assert cache.get(f"pdf_task_lock:{d.pk}")
        r = c.post(_url(d, "/pdf"))
        assert r.status_code == 200 and r.json()["avviato"] is False
    delay.assert_called_once_with(d.pk, mock.ANY)
    mail.assert_called_once()
    r = c.get(_url(d, "/pdf"))
    assert r.status_code == 202 and r.json()["stato"] == "in_generazione"


def test_pdf_bloccato_durante_massivo(client_di, diario_drive):
    from apps.exports import tasks

    cache.set(tasks.lock_key_massivo(diario_drive.edizione_id), True, 60)
    with mock.patch.object(tasks.task_genera_pdf_diario, "delay") as delay:
        r = client_di("admin").post(_url(diario_drive, "/pdf"))
    assert r.status_code == 200 and r.json()["stato"] == "bloccato"
    delay.assert_not_called()


def test_pdf_da_cache_drive(client_di, diario_drive):
    from apps.storage_drive.models import DriveFile, TipoFile

    DriveFile.objects.create(drive_file_id="pdf-1", nome="Tigri.pdf", tipo=TipoFile.PDF,
                             diario=diario_drive)
    c = client_di("crp")
    assert c.get(_url(diario_drive, "/pdf/stato")).json()["stato"] == "pronto"
    with mock.patch("apps.diaries.service.scarica_da_drive", return_value=b"%PDF cache"):
        r = c.get(_url(diario_drive, "/pdf"))
    assert r.status_code == 200 and r.content == b"%PDF cache"
    assert 'filename="Tigri.pdf"' in r["Content-Disposition"]
    # Cache corrotta (file rimosso da Drive): eliminata, il PDF torna da generare
    with mock.patch("apps.diaries.service.scarica_da_drive", side_effect=RuntimeError("404")):
        r = c.get(_url(diario_drive, "/pdf"))
    assert r.status_code == 202 and r.json()["stato"] == "da_generare"
    assert not DriveFile.objects.filter(drive_file_id="pdf-1").exists()


# ---------------------------------------------------------------------------
# Cambio referenti
# ---------------------------------------------------------------------------

@pytest.fixture
def nuovi_soci(org):
    return {
        "ragazzo": _socio(org, "720001", "ragazzo", "Ragazzo"),
        "capo": _socio(org, "720002", "capo", "Capo"),
        "provvisorio": _socio(org, "720003", "capo", "Provv", provvisorio=True),
    }


@pytest.mark.parametrize("ruolo,stato,atteso", [
    ("crp", StatoDiario.NON_INIZIATO, 200),
    ("crp", StatoDiario.IN_COMPILAZIONE, 200),
    ("crp", StatoDiario.RELAZIONE_FINALE, 403),
    ("admin", StatoDiario.RELAZIONE_FINALE, 200),
    ("segreteria", StatoDiario.INVIATO, 403),
    ("csq", StatoDiario.IN_COMPILAZIONE, 403),
    ("estraneo", StatoDiario.IN_COMPILAZIONE, 403),
    ("anonimo", StatoDiario.IN_COMPILAZIONE, 401),
])
def test_cambia_csq_permessi(client_di, diario, nuovi_soci, ruolo, stato, atteso):
    _stato(diario, stato)
    r = client_di(ruolo).post(_url(diario, "/cambia-csq"),
                              **json_body({"socio_id": nuovi_soci["ragazzo"].pk}))
    assert r.status_code == atteso
    diario.refresh_from_db()
    assert (diario.csq_id == nuovi_soci["ragazzo"].pk) is (atteso == 200)


def test_cambia_csq_risposta_e_validazione(client_di, diario, nuovi_soci, utenti):
    c = client_di("crp")
    r = c.post(_url(diario, "/cambia-csq"), **json_body({"socio_id": nuovi_soci["capo"].pk}))
    assert r.status_code == 422 and "socio_id" in r.json()["errori"]
    r = c.post(_url(diario, "/cambia-csq"), **json_body({"socio_id": nuovi_soci["ragazzo"].pk}))
    assert r.json()["nuovo"]["id"] == nuovi_soci["ragazzo"].pk
    assert r.json()["precedente"]["id"] == utenti["csq"].socio.pk
    assert "sostituisce" in r.json()["detail"]


@pytest.mark.parametrize("ruolo,atteso", [
    ("admin", 200), ("incaricato_eg", 200), ("crp", 403), ("csq", 403), ("anonimo", 401),
])
def test_cambia_crp(client_di, diario, nuovi_soci, ruolo, atteso):
    r = client_di(ruolo).post(_url(diario, "/cambia-crp"), **json_body({"socio_id": nuovi_soci["capo"].pk}))
    assert r.status_code == atteso


def test_cambia_crp_validazione_e_stato(client_di, diario, nuovi_soci):
    c = client_di("admin")
    for socio in ("ragazzo", "provvisorio"):
        r = c.post(_url(diario, "/cambia-crp"), **json_body({"socio_id": nuovi_soci[socio].pk}))
        assert r.status_code == 422
    _stato(diario, StatoDiario.INVIATO)
    r = c.post(_url(diario, "/cambia-crp"), **json_body({"socio_id": nuovi_soci["capo"].pk}))
    assert r.status_code == 403


def test_cambia_crp_reparto(client_di, diario, org, edizione, nuovi_soci):
    from apps.editions.models import Edizione

    altra = Edizione.objects.create(anno=2097)
    inviato = Diario.objects.create(edizione=altra, squadriglia=org["squadriglia"],
                                    stato=StatoDiario.INVIATO, crp=diario.crp)
    url = f"/api/v1/diari/reparti/{org['reparto'].pk}/cambia-crp"
    c = client_di("segreteria")
    r = c.get(url)
    assert r.status_code == 200 and [d["id"] for d in r.json()["diari"]] == [diario.pk]
    r = c.post(url, **json_body({"socio_id": nuovi_soci["capo"].pk}))
    assert r.status_code == 200 and r.json()["diari_aggiornati"] == 1
    diario.refresh_from_db()
    inviato.refresh_from_db()
    assert diario.crp_id == nuovi_soci["capo"].pk and inviato.crp_id != nuovi_soci["capo"].pk
    assert client_di("crp").get(url).status_code == 403
    assert client_di("crp").post(url, **json_body({"socio_id": nuovi_soci["capo"].pk})).status_code == 403
    assert client_di("anonimo").get(url).status_code == 401
    assert c.get("/api/v1/diari/reparti/999999/cambia-crp").status_code == 404
    r = c.post(url, **json_body({"socio_id": nuovi_soci["ragazzo"].pk}))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Regole condivise
# ---------------------------------------------------------------------------

def test_pwa_put_anagrafica_rinomina_cartelle_drive(client_di, diario):
    """Il rename della squadriglia da PWA/API rinomina anche le cartelle Drive (come il web)."""
    diario.edizione.drive_oauth_account = "drive@test.it"
    diario.edizione.save()
    diario.drive_folder_allegati_id = "cartella-1"
    diario.save()
    servizio = mock.MagicMock()
    with mock.patch("apps.storage_drive.service._get_credenziali"), \
            mock.patch("apps.storage_drive.service._build_drive_service", return_value=servizio):
        r = client_di("csq").put(_url(diario, "/anagrafica"), **json_body({"version": 0, "data": ANAGRAFICA}))
    assert r.status_code == 200
    servizio.files.return_value.update.assert_called_once()
    assert servizio.files.return_value.update.call_args.kwargs["fileId"] == "cartella-1"
