"""Regressione: i posti d'azione della missione si leggono da `missione.posti_azione`
(related_name di PostoAzioneMissione), non da `posti_azione_missione`."""
import pytest
from django.test import Client

from apps.diaries.models import Diario, Missione, PostoAzioneMissione
from apps.exports.service import genera_export_diari


@pytest.fixture
def missione(diario):
    m = Missione.objects.create(diario=diario, titolo="Missione al faro")
    PostoAzioneMissione.objects.create(missione=m, descrizione="Cartografia del sentiero")
    return m


@pytest.mark.django_db
def test_export_diari_include_posti_azione_missione(missione, user_admin):
    contenuto, _, _ = genera_export_diari(
        Diario.objects.filter(pk=missione.diario_id), user_admin, "csv"
    )
    assert "Cartografia del sentiero" in contenuto.decode("utf-8-sig")


@pytest.mark.django_db
def test_api_v1_dettaglio_diario_posti_azione_missione(missione, user_admin):
    c = Client()
    c.force_login(user_admin)
    r = c.get(f"/api/v1/diari/{missione.diario_id}")
    assert r.status_code == 200
    assert r.json()["missione"]["posti_azione"] == [{"descrizione": "Cartografia del sentiero"}]
