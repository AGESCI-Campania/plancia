"""API aggiornamenti del server (solo Admin): release, richiesta con riautenticazione, stato."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.core.cache import cache

from apps.aggiornamenti import services
from apps.aggiornamenti.models import ReleaseGitHub, RichiestaAggiornamento, StatoRichiesta
from apps.api.tests.conftest import json_body
from apps.siteconfig.versione import versione_installata

pytestmark = pytest.mark.django_db

NON_ADMIN = ("segreteria", "incaricato_eg", "pgv", "crp", "csq")


@pytest.fixture(autouse=True)
def cartella(settings, tmp_path):
    cache.clear()
    settings.AGGIORNAMENTI_DIR = tmp_path / "aggiornamenti"
    yield settings.AGGIORNAMENTI_DIR
    cache.clear()


@pytest.fixture
def release(db):
    r = ReleaseGitHub.get()
    r.versione = "v99.0.0"
    r.nome = "Plancia 99"
    r.note = "## Novità\n- tutto"
    r.url = "https://github.com/AGESCI-Campania/plancia/releases/tag/v99.0.0"
    r.save()
    return r


@pytest.fixture
def admin_riautenticato(client_di):
    """Client Admin che ha appena fatto la riautenticazione headless con la password."""
    c = client_di("admin")
    r = c.post("/_allauth/browser/v1/auth/reauthenticate",
               **json_body({"password": "pw-test-123"}))
    assert r.status_code == 200, r.content
    return c


def _risposta_github(status=200, **dati):
    corpo = {"tag_name": "v99.1.0", "name": "Plancia 99.1", "body": "note",
              "published_at": "2026-11-10T10:00:00Z",
              "html_url": "https://github.com/x/releases/v99.1.0", **dati}
    return SimpleNamespace(status_code=status, json=lambda: corpo)


# ── Permessi ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ruolo", NON_ADMIN)
def test_solo_admin(client_di, release, ruolo):
    c = client_di(ruolo)
    assert c.get("/api/v1/aggiornamenti").status_code == 403
    assert c.post("/api/v1/aggiornamenti/controlla").status_code == 403
    assert c.post("/api/v1/aggiornamenti/richiesta",
                  **json_body({"versione": "v99.0.0"})).status_code == 403
    assert c.get("/api/v1/aggiornamenti/stato").status_code == 403
    assert c.get("/api/v1/aggiornamenti/storico").status_code == 403
    assert c.post("/api/v1/aggiornamenti/richiesta/annulla").status_code == 403


def test_anonimo(client_di):
    assert client_di("anonimo").get("/api/v1/aggiornamenti").status_code == 401
    assert client_di("anonimo").post("/api/v1/aggiornamenti/richiesta",
                                     **json_body({"versione": "v99.0.0"})).status_code == 401


# ── Riepilogo e controllo release ───────────────────────────────────────────


def test_riepilogo(client_di, release):
    r = client_di("admin").get("/api/v1/aggiornamenti")
    assert r.status_code == 200
    dati = r.json()
    assert dati["installata"] == versione_installata()
    assert dati["ultima"]["versione"] == "v99.0.0"
    assert dati["ultima"]["note"].startswith("## Novità")
    assert dati["aggiornamento_disponibile"] is True
    assert dati["richiesta_in_corso"] is None


def test_riepilogo_senza_release(client_di):
    r = client_di("admin").get("/api/v1/aggiornamenti")
    assert r.json()["ultima"] is None and r.json()["aggiornamento_disponibile"] is False


def test_controlla_ora(client_di, monkeypatch, settings):
    chiamate = []

    def finto_get(url, headers, timeout):
        chiamate.append((url, headers, timeout))
        return _risposta_github()

    import requests
    monkeypatch.setattr(requests, "get", finto_get)
    settings.GITHUB_TOKEN_RELEASES = "tok"
    r = client_di("admin").post("/api/v1/aggiornamenti/controlla")
    assert r.status_code == 200
    assert r.json()["ultima"]["versione"] == "v99.1.0"
    assert r.json()["ultima"]["errore"] == ""
    url, headers, timeout = chiamate[0]
    assert url == services.URL_ULTIMA_RELEASE and timeout == services.TIMEOUT_GITHUB
    assert headers["Authorization"] == "Bearer tok"


def test_controlla_errore_non_solleva(monkeypatch, release):
    import requests

    def esplode(*a, **k):
        raise requests.ConnectionError("rete giù")

    monkeypatch.setattr(requests, "get", esplode)
    from apps.aggiornamenti.tasks import controlla_ultima_release

    assert controlla_ultima_release() == "v99.0.0"  # la release nota resta
    release.refresh_from_db()
    assert "rete giù" in release.errore and release.controllata_at is not None

    monkeypatch.setattr(requests, "get", lambda *a, **k: _risposta_github(status=403))
    assert "403" in services.controlla_ultima_release().errore


def test_task_nello_schedule_beat(settings):
    voci = {v["task"] for v in settings.CELERY_BEAT_SCHEDULE.values()}
    assert "aggiornamenti.controlla_ultima_release" in voci


# ── Richiesta ───────────────────────────────────────────────────────────────


def test_richiesta_senza_riautenticazione(client_di, release, cartella):
    r = client_di("admin").post("/api/v1/aggiornamenti/richiesta",
                                **json_body({"versione": "v99.0.0"}))
    assert r.status_code == 401
    assert r.json()["riautenticazione_richiesta"] is True
    assert {"id": "reauthenticate"} in r.json()["flussi"]
    assert not RichiestaAggiornamento.objects.exists()
    assert not (cartella / services.FILE_RICHIESTA).exists()


def test_richiesta_scrive_il_file(admin_riautenticato, utenti, release, cartella):
    r = admin_riautenticato.post("/api/v1/aggiornamenti/richiesta",
                                 **json_body({"versione": "v99.0.0"}))
    assert r.status_code == 201, r.content
    richiesta = RichiestaAggiornamento.objects.get()
    assert richiesta.stato == StatoRichiesta.IN_ATTESA
    assert richiesta.richiesta_da == utenti["admin"]
    assert richiesta.versione_partenza == versione_installata()
    contenuto = json.loads((cartella / services.FILE_RICHIESTA).read_text())
    assert contenuto["id"] == richiesta.pk
    assert contenuto["versione"] == "v99.0.0"
    assert contenuto["richiesta_da"] == "admin@test.it"
    assert contenuto["richiesta_at"]
    assert not list(cartella.glob(".*.tmp"))  # nessun file temporaneo rimasto

    # una seconda richiesta mentre la prima è aperta → 409
    r = admin_riautenticato.post("/api/v1/aggiornamenti/richiesta",
                                 **json_body({"versione": "v99.0.0"}))
    assert r.status_code == 409
    r = admin_riautenticato.get("/api/v1/aggiornamenti")
    assert r.json()["richiesta_in_corso"]["id"] == richiesta.pk


@pytest.mark.parametrize("versione", ["99.0.0", "v99.0", "latest", "v99.0.0;rm"])
def test_richiesta_formato_non_valido(admin_riautenticato, release, versione):
    r = admin_riautenticato.post("/api/v1/aggiornamenti/richiesta",
                                 **json_body({"versione": versione}))
    assert r.status_code == 422 and "versione" in r.json()["errori"]


def test_richiesta_non_ultima_o_non_successiva(admin_riautenticato, release):
    r = admin_riautenticato.post("/api/v1/aggiornamenti/richiesta",
                                 **json_body({"versione": "v98.0.0"}))
    assert r.status_code == 422
    release.versione = "v0.0.1"
    release.save()
    r = admin_riautenticato.post("/api/v1/aggiornamenti/richiesta",
                                 **json_body({"versione": "v0.0.1"}))
    assert r.status_code == 422
    assert "successiva" in r.json()["errori"]["versione"][0]
    assert not RichiestaAggiornamento.objects.exists()


def test_richiesta_bloccata_se_runner_occupato(admin_riautenticato, release, cartella):
    cartella.mkdir(parents=True)
    (cartella / services.FILE_IN_CORSO).write_text("{}")
    r = admin_riautenticato.post("/api/v1/aggiornamenti/richiesta",
                                 **json_body({"versione": "v99.0.0"}))
    assert r.status_code == 409


def test_riautenticazione_scaduta(admin_riautenticato, release, settings):
    settings.ACCOUNT_REAUTHENTICATION_TIMEOUT = 0
    r = admin_riautenticato.post("/api/v1/aggiornamenti/richiesta",
                                 **json_body({"versione": "v99.0.0"}))
    assert r.status_code == 401


# ── Stato, storico, annullamento ────────────────────────────────────────────


def _richiesta(utenti, **kw) -> RichiestaAggiornamento:
    return RichiestaAggiornamento.objects.create(
        versione="v99.0.0", versione_partenza="2.4.1", richiesta_da=utenti["admin"],
        richiesta_da_email="admin@test.it", **kw,
    )


def test_stato_avanzamento_e_completamento(client_di, utenti, cartella):
    richiesta = _richiesta(utenti)
    cartella.mkdir(parents=True)
    stato = {"id": richiesta.pk, "versione": "v99.0.0", "fase": "build",
             "messaggio": "Costruzione delle immagini", "percentuale": 40, "esito": None,
             "aggiornato_at": "2026-11-16T21:00:00+01:00", "log": ["riga 1", "riga 2"]}
    (cartella / services.FILE_STATO).write_text(json.dumps(stato))

    r = client_di("admin").get("/api/v1/aggiornamenti/stato")
    assert r.status_code == 200
    dati = r.json()
    assert dati["in_corso"] is True
    assert dati["richiesta"]["stato"] == "in_corso"
    assert dati["richiesta"]["percentuale"] == 40
    assert dati["richiesta"]["log"] == "riga 1\nriga 2"
    assert dati["stato"]["fase"] == "build"

    stato.update(fase="completato", esito="completato", percentuale=100,
                 messaggio="Aggiornato a v99.0.0")
    (cartella / services.FILE_STATO).write_text(json.dumps(stato))
    r = client_di("admin").get("/api/v1/aggiornamenti/stato")
    assert r.json()["in_corso"] is False
    richiesta.refresh_from_db()
    assert richiesta.stato == StatoRichiesta.COMPLETATO
    assert richiesta.completato_at.isoformat().startswith("2026-11-16T20:00")

    # lo storico chiuso non si riscrive con uno stato successivo
    stato.update(esito="fallito")
    (cartella / services.FILE_STATO).write_text(json.dumps(stato))
    client_di("admin").get("/api/v1/aggiornamenti/stato")
    richiesta.refresh_from_db()
    assert richiesta.stato == StatoRichiesta.COMPLETATO

    r = client_di("admin").get("/api/v1/aggiornamenti/storico")
    assert r.json()["count"] == 1
    assert r.json()["items"][0]["richiesta_da"] == "admin@test.it"


def test_stato_presa_in_carico_e_file_illeggibile(client_di, utenti, cartella):
    richiesta = _richiesta(utenti)
    cartella.mkdir(parents=True)
    (cartella / services.FILE_STATO).write_text("{non json")
    (cartella / services.FILE_IN_CORSO).write_text("{}")
    r = client_di("admin").get("/api/v1/aggiornamenti/stato")
    assert r.status_code == 200
    assert r.json()["stato"] is None
    richiesta.refresh_from_db()
    assert richiesta.stato == StatoRichiesta.IN_CORSO


def test_stato_raggiungibile_in_manutenzione(client_di, utenti):
    from apps.siteconfig.manutenzione import imposta_manutenzione

    imposta_manutenzione(True)
    assert client_di("admin").get("/api/v1/aggiornamenti/stato").status_code == 200
    # il bypass non apre l'endpoint: i non Admin restano fuori
    assert client_di("segreteria").get("/api/v1/aggiornamenti/stato").status_code == 403


def test_annulla(client_di, utenti, cartella):
    richiesta = _richiesta(utenti)
    cartella.mkdir(parents=True)
    (cartella / services.FILE_RICHIESTA).write_text("{}")
    r = client_di("admin").post("/api/v1/aggiornamenti/richiesta/annulla")
    assert r.status_code == 200 and r.json()["stato"] == "annullato"
    assert not (cartella / services.FILE_RICHIESTA).exists()
    assert client_di("admin").post("/api/v1/aggiornamenti/richiesta/annulla").status_code == 422

    _richiesta(utenti, stato=StatoRichiesta.IN_CORSO)
    (cartella / services.FILE_IN_CORSO).write_text("{}")
    assert client_di("admin").post("/api/v1/aggiornamenti/richiesta/annulla").status_code == 409
    richiesta.refresh_from_db()
    assert richiesta.stato == StatoRichiesta.ANNULLATO


def test_versioni():
    assert services.e_successiva("v2.10.0", "2.9.9")
    assert not services.e_successiva("v2.4.1", "2.4.1")
    assert not services.e_successiva("v2.4.0", "2.4.1")
    assert services.versione_tuple("2.4.1") == (2, 4, 1)
    assert services.versione_tuple("v2.4") is None
