"""API importazioni: lancio, storico, dettaglio, scarti, riconciliazione, riprova."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.api.tests.conftest import json_body
from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch, TipoImport

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
NON_STAFF = ("pgv", "crp", "csq")


@pytest.fixture
def task_finti(monkeypatch, settings, tmp_path):
    """Sostituisce i task Celery con registratori e salva i file in una cartella temporanea."""
    settings.MEDIA_ROOT = tmp_path
    chiamate: list[tuple] = []

    def _finto(nome):
        def delay(*args, **kwargs):
            chiamate.append((nome, args, kwargs))
            return SimpleNamespace(id=f"task-{nome}")
        return delay

    from apps.imports import tasks

    monkeypatch.setattr(tasks.task_lancia_import, "delay", _finto("lancia"))
    monkeypatch.setattr(tasks.task_import_risposte_eg, "delay", _finto("risposte_eg"))
    return chiamate


@pytest.fixture
def log_squadriglie(db, edizione):
    log = LogImportazione.objects.create(
        tipo=TipoImport.SQUADRIGLIE, file_nome="sq.csv", edizione=edizione,
        totale=3, ok=1, scartati=1, da_riconciliare=1,
    )
    RigaImportazione.objects.create(log=log, numero=1, stato_match=StatoMatch.OK)
    RigaImportazione.objects.create(
        log=log, numero=2, stato_match=StatoMatch.SCARTATA, note="Codice mancante",
        dati_grezzi={"Codice": "", "Squadriglia": "Lupi"},
    )
    RigaImportazione.objects.create(
        log=log, numero=3, stato_match=StatoMatch.DA_RICONCILIARE,
        dati_grezzi={"Codice": "", "EmailReferente": "crp@test.it", "NomeReferente": "TEST, CRP"},
    )
    return log


def _file(nome="capi.csv", contenuto=b"a;b\n1;2\n"):
    return SimpleUploadedFile(nome, contenuto, content_type="text/csv")


# ── Lancio ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ruolo", STAFF)
def test_lancio_coca_staff(client_di, task_finti, ruolo):
    r = client_di(ruolo).post("/api/v1/importazioni/lancia/coca", {"file": _file()})
    assert r.status_code == 202, r.content
    assert r.json()["task_id"] == "task-lancia"
    nome, args, kwargs = task_finti[0]
    assert args == ("coca",) and kwargs["edizione_pk"] is None


def test_lancio_squadriglie_richiede_edizione(client_di, task_finti, edizione):
    c = client_di("segreteria")
    r = c.post("/api/v1/importazioni/lancia/squadriglie", {"file": _file()})
    assert r.status_code == 422
    assert "edizione_pk" in r.json()["errori"]
    r = c.post("/api/v1/importazioni/lancia/squadriglie",
               {"file": _file(), "edizione_pk": str(edizione.pk)})
    assert r.status_code == 202
    assert task_finti[-1][2]["edizione_pk"] == edizione.pk


def test_lancio_risposte_eg(client_di, task_finti):
    r = client_di("admin").post(
        "/api/v1/importazioni/lancia/risposte_eg", {"file": _file("eg.xlsx", b"xx")}
    )
    assert r.status_code == 202
    assert task_finti[0][0] == "risposte_eg"


def test_lancio_errori(client_di, task_finti):
    c = client_di("admin")
    assert c.post("/api/v1/importazioni/lancia/boh", {"file": _file()}).status_code == 422
    r = c.post("/api/v1/importazioni/lancia/coca", {})
    assert r.status_code == 422 and "file" in r.json()["errori"]
    r = c.post("/api/v1/importazioni/lancia/coca", {"file": _file("capi.xlsx")})
    assert r.status_code == 422 and "file" in r.json()["errori"]
    assert task_finti == []


@pytest.mark.parametrize("ruolo", NON_STAFF)
def test_lancio_vietato(client_di, task_finti, ruolo):
    assert client_di(ruolo).post(
        "/api/v1/importazioni/lancia/coca", {"file": _file()}
    ).status_code == 403
    assert task_finti == []


def test_lancio_anonimo(client_di, task_finti):
    r = client_di("anonimo").post("/api/v1/importazioni/lancia/coca", {"file": _file()})
    assert r.status_code == 401


def test_tracciati(client_di):
    r = client_di("incaricato_eg").get("/api/v1/importazioni/tracciati")
    assert r.status_code == 200
    assert {t["chiave"] for t in r.json()} == {"coca", "ragazzi", "squadriglie", "risposte_eg"}
    assert client_di("crp").get("/api/v1/importazioni/tracciati").status_code == 403


# ── Storico e dettaglio ─────────────────────────────────────────────────────


def test_lista_e_dettaglio(client_di, log_squadriglie):
    c = client_di("segreteria")
    r = c.get("/api/v1/importazioni/log")
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert r.json()["items"][0]["edizione_anno"] == 2098

    r = c.get(f"/api/v1/importazioni/log/{log_squadriglie.pk}")
    assert r.status_code == 200
    dati = r.json()
    assert dati["e_squadriglie"] is True
    assert [x["numero"] for x in dati["righe_da_riconciliare"]] == [3]
    assert [x["numero"] for x in dati["righe_scartate"]] == [2]
    assert c.get("/api/v1/importazioni/log/999999").status_code == 404


@pytest.mark.parametrize("ruolo", (*NON_STAFF, "anonimo"))
def test_lista_vietata(client_di, log_squadriglie, ruolo):
    atteso = 401 if ruolo == "anonimo" else 403
    assert client_di(ruolo).get("/api/v1/importazioni/log").status_code == atteso
    assert client_di(ruolo).get(
        f"/api/v1/importazioni/log/{log_squadriglie.pk}"
    ).status_code == atteso


def test_scarti_csv(client_di, log_squadriglie):
    r = client_di("admin").get(f"/api/v1/importazioni/log/{log_squadriglie.pk}/scarti.csv")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/csv")
    assert "attachment" in r["Content-Disposition"]
    testo = r.content.decode("utf-8")
    assert testo.startswith("﻿#,Errore")
    assert "Codice mancante" in testo and "Lupi" in testo
    assert client_di("crp").get(
        f"/api/v1/importazioni/log/{log_squadriglie.pk}/scarti.csv"
    ).status_code == 403


# ── Riconciliazione e riprova ───────────────────────────────────────────────


def test_riconcilia_riga(client_di, log_squadriglie, utenti):
    riga = log_squadriglie.righe.get(numero=3)
    socio = utenti["crp"].socio
    r = client_di("incaricato_eg").post(
        f"/api/v1/importazioni/righe/{riga.pk}/riconcilia", **json_body({"socio_pk": socio.pk})
    )
    assert r.status_code == 200, r.content
    assert r.json()["riga"]["stato_match"] == "ok"
    assert r.json()["log"]["da_riconciliare"] == 0 and r.json()["log"]["ok"] == 2
    riga.refresh_from_db()
    assert riga.socio_match == socio
    # già riconciliata → 422
    r = client_di("incaricato_eg").post(
        f"/api/v1/importazioni/righe/{riga.pk}/riconcilia", **json_body({"socio_pk": socio.pk})
    )
    assert r.status_code == 422


def test_riconcilia_solo_capi(client_di, log_squadriglie, utenti):
    riga = log_squadriglie.righe.get(numero=3)
    c = client_di("admin")
    r = c.post(f"/api/v1/importazioni/righe/{riga.pk}/riconcilia",
               **json_body({"socio_pk": utenti["csq"].socio.pk}))
    assert r.status_code == 422 and "socio_pk" in r.json()["errori"]
    r = c.post(f"/api/v1/importazioni/righe/{riga.pk}/riconcilia",
               **json_body({"socio_pk": 999999}))
    assert r.status_code == 422
    assert c.post("/api/v1/importazioni/righe/999999/riconcilia",
                  **json_body({"socio_pk": 1})).status_code == 404


def test_riconcilia_vietata(client_di, log_squadriglie, utenti):
    riga = log_squadriglie.righe.get(numero=3)
    r = client_di("crp").post(f"/api/v1/importazioni/righe/{riga.pk}/riconcilia",
                              **json_body({"socio_pk": utenti["crp"].socio.pk}))
    assert r.status_code == 403
    riga.refresh_from_db()
    assert riga.stato_match == StatoMatch.DA_RICONCILIARE


def test_riprova_anomalie(client_di, log_squadriglie):
    r = client_di("segreteria").post(f"/api/v1/importazioni/log/{log_squadriglie.pk}/riprova")
    assert r.status_code == 200, r.content
    assert r.json()["risolte"] == 1 and r.json()["ancora_aperte"] == 0
    assert r.json()["log"]["da_riconciliare"] == 0
    # niente più da riprovare
    r = client_di("segreteria").post(f"/api/v1/importazioni/log/{log_squadriglie.pk}/riprova")
    assert r.json()["messaggio"] == "Nessuna anomalia da riprovare."


def test_riprova_non_risolta(client_di, log_squadriglie):
    riga = log_squadriglie.righe.get(numero=3)
    riga.dati_grezzi = {"EmailReferente": "nessuno@test.it", "NomeReferente": "NESSUNO, X"}
    riga.save()
    r = client_di("admin").post(f"/api/v1/importazioni/log/{log_squadriglie.pk}/riprova")
    assert r.status_code == 200
    assert r.json()["risolte"] == 0 and r.json()["ancora_aperte"] == 1
    assert "Capi Reparto" in r.json()["messaggio"]


def test_riprova_solo_squadriglie_e_permessi(client_di, log_squadriglie):
    altro = LogImportazione.objects.create(tipo=TipoImport.COCA, file_nome="c.csv")
    assert client_di("admin").post(
        f"/api/v1/importazioni/log/{altro.pk}/riprova"
    ).status_code == 422
    assert client_di("pgv").post(
        f"/api/v1/importazioni/log/{log_squadriglie.pk}/riprova"
    ).status_code == 403
    assert client_di("anonimo").post(
        f"/api/v1/importazioni/log/{log_squadriglie.pk}/riprova"
    ).status_code == 401
