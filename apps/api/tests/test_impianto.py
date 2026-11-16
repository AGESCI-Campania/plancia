"""Impianto comune dell'API: gestori di errore e fixture per ruolo."""
import pytest

from apps.api.tests.conftest import RUOLI_TEST

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("ruolo", RUOLI_TEST)
def test_me_per_ogni_ruolo(client_di, utenti, ruolo):
    r = client_di(ruolo).get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["ruolo"]["chiave"] == utenti[ruolo].ruolo


def test_anonimo_non_autenticato(client_di):
    assert client_di("anonimo").get("/api/v1/me").status_code == 401


def test_pgv_vede_solo_i_diari_assegnati(client_di, diario):
    assert client_di("pgv").get(f"/api/v1/diari/{diario.pk}").status_code in (403, 404)
    assert client_di("crp").get(f"/api/v1/diari/{diario.pk}").status_code == 200
