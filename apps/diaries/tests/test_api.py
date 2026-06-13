# apps/diaries/tests/test_api.py
"""Test delle API JSON del Diario (Fase 2 — v2-offline)."""
import json

import pytest
from django.test import Client

from apps.diaries.models import (
    Anagrafica,
    Diario,
    EsitoSpecialita,
    Impresa,
    MembroSq,
    Missione,
    PostoAzione,
    Presentazione,
    StatoDiario,
    TipoDiario,
    TipoEsito,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(client: Client, url: str):
    return client.get(url, HTTP_ACCEPT="application/json")


def api_put(client: Client, url: str, payload: dict):
    return client.put(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )


def _valid_anagrafica_payload(version: int = 0) -> dict:
    return {
        "version": version,
        "data": {
            "squadriglia_nome": "Pantere",
            "tipo_diario": "nuovo",
            "crp_nome": "Mario", "crp_cognome": "Rossi",
            "crp_email": "mario@test.it", "crp_cell": "333111222",
            "csq_nome": "Luigi", "csq_cognome": "Bianchi",
            "csq_email": "luigi@test.it", "csq_cell": "333444555",
            "specialita": "Campismo",
            "partecipa_evento": True,
        },
    }


# ---------------------------------------------------------------------------
# GET /api/diari/<pk>/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_status_unauthenticated(diario):
    c = Client()
    r = api_get(c, f"/api/diari/{diario.pk}/")
    assert r.status_code == 401
    assert r.json()["error"] == "unauthenticated"


@pytest.mark.django_db
def test_status_forbidden(diario, user_crp):
    """Un CRP di un altro reparto non può accedere."""
    from apps.accounts.models import User, Ruolo
    from apps.org.models import Socio
    altro_socio = Socio.objects.create(
        codice_socio="899999", nome="Altro", cognome="CRP",
        email="altro@test.it", categoria="capo",
        zona=diario.squadriglia.reparto.gruppo.zona,
        gruppo=diario.squadriglia.reparto.gruppo,
    )
    altro_crp = User.objects.create_user(
        username="altro_crp", email="altro@test.it", password="x",
        ruolo=Ruolo.CRP,
    )
    altro_crp.socio = altro_socio
    altro_crp.save()

    c = Client()
    c.force_login(altro_crp)
    r = api_get(c, f"/api/diari/{diario.pk}/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_status_ok_csq(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    r = api_get(c, f"/api/diari/{diario.pk}/")
    assert r.status_code == 200
    data = r.json()
    assert data["stato"] == StatoDiario.IN_COMPILAZIONE
    assert data["puo_editare"] is True
    assert isinstance(data["imprese"], list)
    assert data["has_anagrafica"] is False


@pytest.mark.django_db
def test_status_not_found(user_csq):
    c = Client()
    c.force_login(user_csq)
    r = api_get(c, "/api/diari/999999/")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/diari/<pk>/modulo/anagrafica/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_anagrafica_vuota(diario, user_csq):
    """GET restituisce version=0 e campi vuoti quando l'anagrafica non esiste ancora."""
    c = Client()
    c.force_login(user_csq)
    r = api_get(c, f"/api/diari/{diario.pk}/modulo/anagrafica/")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 0
    assert body["data"]["csq_nome"] == ""
    assert body["data"]["specialita"] == ""
    assert body["data"]["squadriglia_nome"] == diario.squadriglia.nome
    assert body["data"]["tipo_diario"] == diario.tipo


@pytest.mark.django_db
def test_get_anagrafica_esistente(diario, user_csq):
    Anagrafica.objects.create(diario=diario, csq_nome="Luigi", version=3)
    c = Client()
    c.force_login(user_csq)
    r = api_get(c, f"/api/diari/{diario.pk}/modulo/anagrafica/")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 3
    assert body["data"]["csq_nome"] == "Luigi"


# ---------------------------------------------------------------------------
# PUT /api/diari/<pk>/modulo/anagrafica/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_put_anagrafica_crea(diario, user_csq):
    """PUT con version=0 crea l'anagrafica e ritorna version=1."""
    c = Client()
    c.force_login(user_csq)
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", _valid_anagrafica_payload(0))
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    assert body["data"]["csq_nome"] == "Luigi"
    assert body["data"]["specialita"] == "Campismo"
    ana = Anagrafica.objects.get(diario=diario)
    assert ana.version == 1
    assert ana.csq_nome == "Luigi"


@pytest.mark.django_db
def test_put_anagrafica_aggiorna(diario, user_csq):
    """PUT su record esistente incrementa la version."""
    Anagrafica.objects.create(diario=diario, csq_nome="Vecchio", version=2)
    c = Client()
    c.force_login(user_csq)
    payload = _valid_anagrafica_payload(2)
    payload["data"]["csq_nome"] = "Nuovo"
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", payload)
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 3
    assert body["data"]["csq_nome"] == "Nuovo"


@pytest.mark.django_db
def test_put_anagrafica_conflict(diario, user_csq):
    """Version stale → 409 con server_version."""
    Anagrafica.objects.create(diario=diario, version=5)
    c = Client()
    c.force_login(user_csq)
    payload = _valid_anagrafica_payload(3)  # stale: server è a 5
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", payload)
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "conflict"
    assert body["server_version"] == 5


@pytest.mark.django_db
def test_put_anagrafica_conflict_nuovo_record(diario, user_csq):
    """Se il record non esiste e il client manda version!=0 → 409."""
    c = Client()
    c.force_login(user_csq)
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", _valid_anagrafica_payload(1))
    assert r.status_code == 409
    assert r.json()["server_version"] == 0


@pytest.mark.django_db
def test_put_anagrafica_stato_inviato_forbidden(diario, user_csq):
    """Diario già inviato → 403."""
    diario.stato = StatoDiario.INVIATO
    diario.save(update_fields=["stato"])
    c = Client()
    c.force_login(user_csq)
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", _valid_anagrafica_payload(0))
    assert r.status_code == 403


@pytest.mark.django_db
def test_put_anagrafica_transita_non_iniziato(diario, user_csq):
    """PUT su diario NON_INIZIATO deve transitare automaticamente a IN_COMPILAZIONE."""
    diario.stato = StatoDiario.NON_INIZIATO
    diario.save(update_fields=["stato"])
    c = Client()
    c.force_login(user_csq)
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", _valid_anagrafica_payload(0))
    assert r.status_code == 200
    diario.refresh_from_db()
    assert diario.stato == StatoDiario.IN_COMPILAZIONE


@pytest.mark.django_db
def test_put_anagrafica_email_ignorata_per_csq(diario, user_csq):
    """Il CSQ non può modificare le email (vengono ignorate silenziosamente)."""
    Anagrafica.objects.create(diario=diario, crp_email="originale@test.it", version=0)
    c = Client()
    c.force_login(user_csq)
    payload = _valid_anagrafica_payload(0)
    payload["data"]["crp_email"] = "modificata@test.it"
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", payload)
    assert r.status_code == 200
    ana = Anagrafica.objects.get(diario=diario)
    assert ana.crp_email == "originale@test.it"


@pytest.mark.django_db
def test_put_anagrafica_email_modificabile_da_admin(diario, user_admin):
    """Lo staff può modificare le email."""
    Anagrafica.objects.create(diario=diario, crp_email="originale@test.it", version=0)
    c = Client()
    c.force_login(user_admin)
    payload = _valid_anagrafica_payload(0)
    payload["data"]["crp_email"] = "nuova@test.it"
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", payload)
    assert r.status_code == 200
    ana = Anagrafica.objects.get(diario=diario)
    assert ana.crp_email == "nuova@test.it"


@pytest.mark.django_db
def test_put_anagrafica_rinomina_squadriglia(diario, user_csq):
    """PUT con squadriglia_nome diverso rinomina la squadriglia nel DB."""
    assert diario.squadriglia.nome == "Tigri"
    c = Client()
    c.force_login(user_csq)
    payload = _valid_anagrafica_payload(0)
    payload["data"]["squadriglia_nome"] = "Aquile"
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", payload)
    assert r.status_code == 200
    diario.squadriglia.refresh_from_db()
    assert diario.squadriglia.nome == "Aquile"
    assert r.json()["data"]["squadriglia_nome"] == "Aquile"


@pytest.mark.django_db
def test_put_anagrafica_validation_error(diario, user_csq):
    """Dati non validi → 400 con errors."""
    c = Client()
    c.force_login(user_csq)
    payload = _valid_anagrafica_payload(0)
    payload["data"]["tipo_diario"] = "invalido"
    payload["data"]["crp_email"] = "non-una-email"
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", payload)
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "validation"
    assert "tipo_diario" in body["errors"]
    assert "crp_email" in body["errors"]


@pytest.mark.django_db
def test_put_anagrafica_missing_version(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", {"data": {}})
    assert r.status_code == 400
    assert r.json()["error"] == "version_required"


@pytest.mark.django_db
def test_put_anagrafica_missing_data(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", {"version": 0})
    assert r.status_code == 400
    assert r.json()["error"] == "data_required"


@pytest.mark.django_db
def test_put_anagrafica_aggiorna_tipo_diario(diario, user_csq):
    """PUT con tipo_diario='rinnovo' aggiorna Diario.tipo."""
    assert diario.tipo == TipoDiario.NUOVO
    c = Client()
    c.force_login(user_csq)
    payload = _valid_anagrafica_payload(0)
    payload["data"]["tipo_diario"] = "rinnovo"
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/anagrafica/", payload)
    assert r.status_code == 200
    diario.refresh_from_db()
    assert diario.tipo == TipoDiario.RINNOVO


# ---------------------------------------------------------------------------
# GET /api/diari/<pk>/modulo/presentazione/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_presentazione_vuota(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    r = api_get(c, f"/api/diari/{diario.pk}/modulo/presentazione/")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 0
    assert body["data"]["cosa_sappiamo_fare"] == ""
    assert body["data"]["membri"] == []


@pytest.mark.django_db
def test_put_presentazione_crea_con_membri(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 0,
        "data": {
            "cosa_sappiamo_fare": "Sappiamo fare molte cose.",
            "membri": [
                {"id": None, "nome": "Mario Rossi", "ruolo": "csq", "sentiero": "competenza"},
                {"id": None, "nome": "Lucia Bianchi", "ruolo": "squadrigliere", "sentiero": "scoperta"},
            ],
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/presentazione/", payload)
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    assert len(body["data"]["membri"]) == 2
    assert MembroSq.objects.filter(presentazione__diario=diario).count() == 2


@pytest.mark.django_db
def test_put_presentazione_update_delete_membro(diario, user_csq):
    """Aggiorna un membro esistente e cancella quello non inviato."""
    pres = Presentazione.objects.create(diario=diario, version=1)
    m1 = MembroSq.objects.create(presentazione=pres, nome="Mario", ruolo="csq", sentiero="scoperta")
    m2 = MembroSq.objects.create(presentazione=pres, nome="Lucia", ruolo="squadrigliere", sentiero="scoperta")

    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 1,
        "data": {
            "cosa_sappiamo_fare": "Aggiornato",
            "membri": [
                {"id": m1.pk, "nome": "Mario Aggiornato", "ruolo": "vcsq", "sentiero": "competenza"},
                # m2 non incluso → deve essere cancellato
            ],
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/presentazione/", payload)
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert MembroSq.objects.filter(presentazione=pres).count() == 1
    m1.refresh_from_db()
    assert m1.nome == "Mario Aggiornato"
    assert m1.ruolo == "vcsq"


@pytest.mark.django_db
def test_put_presentazione_conflict(diario, user_csq):
    Presentazione.objects.create(diario=diario, version=3)
    c = Client()
    c.force_login(user_csq)
    payload = {"version": 1, "data": {"cosa_sappiamo_fare": "X", "membri": []}}
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/presentazione/", payload)
    assert r.status_code == 409
    assert r.json()["server_version"] == 3


@pytest.mark.django_db
def test_put_presentazione_membro_invalido(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 0,
        "data": {
            "cosa_sappiamo_fare": "",
            "membri": [{"id": None, "nome": "X", "ruolo": "ruolo_inesistente", "sentiero": "scoperta"}],
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/presentazione/", payload)
    assert r.status_code == 400
    assert "membri" in r.json()["errors"]


# ---------------------------------------------------------------------------
# GET / PUT /api/diari/<pk>/modulo/impresa/<numero>/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_impresa_vuota(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    r = api_get(c, f"/api/diari/{diario.pk}/modulo/impresa/1/")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 0
    assert body["data"]["titolo"] == ""
    assert body["data"]["posti_azione"] == []
    assert body["data"]["specialita"] == []
    assert body["data"]["brevetti"] == []


@pytest.mark.django_db
def test_put_impresa_crea(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 0,
        "data": {
            "titolo": "La nostra impresa",
            "data_inizio": "2025-03-01",
            "data_fine": "2025-04-15",
            "perche": "Perché ci piaceva.",
            "come": "Con entusiasmo.",
            "cosa": "Abbiamo costruito qualcosa.",
            "link_esterno": "",
            "posti_azione": [
                {"id": None, "chi": "Mario", "cosa": "Fotografia"},
            ],
            "specialita": [
                {"id": None, "chi": "Luigi", "nome": "Fotografo", "stato": "conquistata"},
            ],
            "brevetti": [],
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/impresa/1/", payload)
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    assert body["data"]["titolo"] == "La nostra impresa"
    assert body["data"]["data_inizio"] == "2025-03-01"
    assert len(body["data"]["posti_azione"]) == 1
    assert len(body["data"]["specialita"]) == 1
    assert body["data"]["specialita"][0]["nome"] == "Fotografo"
    assert Impresa.objects.filter(diario=diario, numero=1).exists()


@pytest.mark.django_db
def test_put_impresa_sync_nested(diario, user_csq):
    """Update di un posto_azione e cancellazione di un esito specialità."""
    imp = Impresa.objects.create(diario=diario, numero=1, titolo="Vecchia", version=1)
    p1 = PostoAzione.objects.create(impresa=imp, chi="Vecchio", cosa="Cosa")
    e1 = EsitoSpecialita.objects.create(
        impresa=imp, tipo=TipoEsito.SPECIALITA, chi="", nome="Fotografo", stato="in_cammino"
    )

    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 1,
        "data": {
            "titolo": "Aggiornata",
            "data_inizio": None, "data_fine": None,
            "perche": "", "come": "", "cosa": "", "link_esterno": "",
            "posti_azione": [{"id": p1.pk, "chi": "Aggiornato", "cosa": "Nuova cosa"}],
            "specialita": [],  # e1 rimosso
            "brevetti": [],
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/impresa/1/", payload)
    assert r.status_code == 200
    assert r.json()["version"] == 2
    p1.refresh_from_db()
    assert p1.chi == "Aggiornato"
    assert not EsitoSpecialita.objects.filter(pk=e1.pk).exists()


@pytest.mark.django_db
def test_put_impresa_conflict(diario, user_csq):
    Impresa.objects.create(diario=diario, numero=1, version=4)
    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 2, "data": {
            "titolo": "", "data_inizio": None, "data_fine": None,
            "perche": "", "come": "", "cosa": "", "link_esterno": "",
            "posti_azione": [], "specialita": [], "brevetti": [],
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/impresa/1/", payload)
    assert r.status_code == 409
    assert r.json()["server_version"] == 4


@pytest.mark.django_db
def test_put_impresa_data_invalida(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 0,
        "data": {
            "titolo": "", "data_inizio": "non-una-data", "data_fine": None,
            "perche": "", "come": "", "cosa": "", "link_esterno": "",
            "posti_azione": [], "specialita": [], "brevetti": [],
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/impresa/1/", payload)
    assert r.status_code == 400
    assert "data_inizio" in r.json()["errors"]


@pytest.mark.django_db
def test_put_impresa_brevetti_separati_da_specialita(diario, user_csq):
    """Brevetti e specialità sono liste separate e non si mischiano."""
    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 0,
        "data": {
            "titolo": "", "data_inizio": None, "data_fine": None,
            "perche": "", "come": "", "cosa": "", "link_esterno": "",
            "posti_azione": [],
            "specialita": [{"id": None, "chi": "", "nome": "Fotografo", "stato": "in_cammino"}],
            "brevetti": [{"id": None, "chi": "", "nome": "Artista", "stato": "in_cammino"}],
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/impresa/1/", payload)
    assert r.status_code == 200
    impresa = Impresa.objects.get(diario=diario, numero=1)
    assert impresa.esiti_specialita.filter(tipo=TipoEsito.SPECIALITA).count() == 1
    assert impresa.esiti_specialita.filter(tipo=TipoEsito.BREVETTO).count() == 1


# ---------------------------------------------------------------------------
# GET / PUT /api/diari/<pk>/modulo/missione/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_missione_vuota(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    r = api_get(c, f"/api/diari/{diario.pk}/modulo/missione/")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 0
    assert body["data"]["titolo"] == ""
    assert body["data"]["data"] is None


@pytest.mark.django_db
def test_put_missione_crea(diario, user_csq):
    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 0,
        "data": {
            "titolo": "Missione Aquila",
            "data": "2025-05-10",
            "descrizione_svolgimento": "Abbiamo esplorato il bosco.",
        },
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/missione/", payload)
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    assert body["data"]["titolo"] == "Missione Aquila"
    assert body["data"]["data"] == "2025-05-10"
    assert Missione.objects.filter(diario=diario).exists()


@pytest.mark.django_db
def test_put_missione_aggiorna(diario, user_csq):
    Missione.objects.create(diario=diario, titolo="Vecchia", version=2)
    c = Client()
    c.force_login(user_csq)
    payload = {
        "version": 2,
        "data": {"titolo": "Nuova", "data": None, "descrizione_svolgimento": ""},
    }
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/missione/", payload)
    assert r.status_code == 200
    assert r.json()["version"] == 3
    assert Missione.objects.get(diario=diario).titolo == "Nuova"


@pytest.mark.django_db
def test_put_missione_conflict(diario, user_csq):
    Missione.objects.create(diario=diario, version=5)
    c = Client()
    c.force_login(user_csq)
    payload = {"version": 3, "data": {"titolo": "", "data": None, "descrizione_svolgimento": ""}}
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/missione/", payload)
    assert r.status_code == 409
    assert r.json()["server_version"] == 5


@pytest.mark.django_db
def test_put_missione_transita_non_iniziato(diario, user_csq):
    diario.stato = StatoDiario.NON_INIZIATO
    diario.save(update_fields=["stato"])
    c = Client()
    c.force_login(user_csq)
    payload = {"version": 0, "data": {"titolo": "M", "data": None, "descrizione_svolgimento": ""}}
    r = api_put(c, f"/api/diari/{diario.pk}/modulo/missione/", payload)
    assert r.status_code == 200
    diario.refresh_from_db()
    assert diario.stato == StatoDiario.IN_COMPILAZIONE
