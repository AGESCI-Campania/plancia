"""API statistiche: dati della dashboard per zona, solo staff."""
from __future__ import annotations

import pytest
from django.utils import timezone

from apps.evaluations.models import EsitoValutazione, Valutazione
from apps.helpdesk.models import Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cache_pulita():
    """Il rate limiting API conta le richieste in cache (per IP): azzerala a ogni test,
    altrimenti nella suite completa si superano le 60 richieste/minuto (429)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def dati(diario, utenti, org, edizione):
    from apps.diaries.models import Diario, StatoDiario

    diario.stato = StatoDiario.APPROVATO
    diario.pubblicato_at = timezone.now()
    diario.save()
    Valutazione.objects.create(diario=diario, esito=EsitoValutazione.APPROVATA)
    Diario.objects.create(
        edizione=edizione, squadriglia=org["squadriglia_altra"], csq=utenti["estraneo"].socio,
        tipo=diario.tipo, stato=StatoDiario.IN_COMPILAZIONE,
        scadenza_riferimento=diario.scadenza_riferimento,
    )
    Ticket.objects.create(aperto_da=utenti["csq"], diario=diario, oggetto="x", corpo="y",
                          categoria="tecnico")
    return diario


@pytest.mark.parametrize("ruolo", ("admin", "segreteria", "incaricato_eg"))
def test_statistiche_staff(client_di, dati, edizione, ruolo):
    r = client_di(ruolo).get("/api/v1/statistiche")
    assert r.status_code == 200, r.content
    corpo = r.json()
    assert corpo["edizione"]["id"] == edizione.pk
    zona = corpo["per_zona"][0]
    assert zona["zona"]["nome"] == "Zona API"
    assert (zona["totale"], zona["approvati"], zona["pubblicati"]) == (2, 1, 1)
    assert zona["percentuale_approvati"] == 50
    assert corpo["globali"]["in_compilazione"] == 1
    assert corpo["ticket"]["totale"] == 1
    tecnico = next(c for c in corpo["ticket"]["per_categoria"] if c["chiave"] == "tecnico")
    assert tecnico["count"] == 1


def test_statistiche_edizione_esplicita_e_vuota(client_di, edizione):
    r = client_di("admin").get("/api/v1/statistiche", {"edizione_id": edizione.pk})
    assert r.status_code == 200
    assert r.json()["per_zona"] == [] and r.json()["globali"]["totale"] == 0


def test_statistiche_senza_edizioni(client_di, utenti):
    r = client_di("admin").get("/api/v1/statistiche")
    assert r.status_code == 200
    assert r.json()["edizione"] is None and r.json()["globali"] is None


@pytest.mark.parametrize("ruolo,atteso", [("pgv", 403), ("crp", 403), ("csq", 403),
                                          ("anonimo", 401)])
def test_statistiche_vietate(client_di, ruolo, atteso):
    assert client_di(ruolo).get("/api/v1/statistiche").status_code == atteso
