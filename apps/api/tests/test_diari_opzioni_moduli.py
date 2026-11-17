"""`GET /api/v1/diari/moduli/opzioni`: scelte dei campi dei moduli per i form della SPA."""
import pytest

from apps.diaries.models import BREVETTI_COMPETENZA, SPECIALITA_INDIVIDUALI, SPECIALITA_SQUADRIGLIA

pytestmark = pytest.mark.django_db


def test_opzioni_moduli_anonimo_401(client_di):
    assert client_di("anonimo").get("/api/v1/diari/moduli/opzioni").status_code == 401


def test_opzioni_moduli(client_di):
    from apps.siteconfig.models import Impostazioni

    imp = Impostazioni.get()
    imp.allegati_max_px = 1600
    imp.save()
    r = client_di("csq").get("/api/v1/diari/moduli/opzioni")
    assert r.status_code == 200
    dati = r.json()
    assert dati["specialita_squadriglia"] == SPECIALITA_SQUADRIGLIA
    assert dati["specialita_individuali"] == SPECIALITA_INDIVIDUALI
    assert dati["brevetti"] == BREVETTI_COMPETENZA
    assert {"valore": "rinnovo", "etichetta": "Rinnovo"} in dati["tipi_diario"]
    assert {"valore": "csq", "etichetta": "Capo Squadriglia"} in dati["ruoli_squadriglia"]
    assert [s["valore"] for s in dati["sentieri"]][-1] == "non_specificato"
    assert {"valore": "in_cammino", "etichetta": "In cammino"} in dati["stati_specialita"]
    assert [m["valore"] for m in dati["moduli_foto"]] == ["impresa_1", "impresa_2", "missione"]
    assert dati["allegati_max_px"] == 1600
    assert dati["allegati_max_mb"] == 20
    assert "image/heic" in dati["allegati_tipi"]
