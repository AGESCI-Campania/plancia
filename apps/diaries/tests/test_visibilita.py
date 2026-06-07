# apps/diaries/tests/test_visibilita.py
"""Test delle regole di visibilità (docs sez. 5 — tre livelli: view, queryset)."""
import pytest
from django.utils import timezone

from apps.accounts.models import Ruolo, User
from apps.diaries.models import (
    Diario,
    ScadenzaRiferimento,
    StatoDiario,
    TipoDiario,
)


@pytest.fixture
def zona(db):
    from apps.org.models import Zona
    return Zona.objects.create(nome="Zona Visib")


@pytest.fixture
def socio_csq(db, zona):
    from apps.org.models import Gruppo, Socio
    gruppo = Gruppo.objects.create(nome="Gruppo V", zona=zona)
    return Socio.objects.create(
        codice_socio="900001", nome="Capo", cognome="Squadriglia",
        email="csq@test.it", categoria="ragazzo", zona=zona, gruppo=gruppo,
    )


@pytest.fixture
def socio_crp(db, zona):
    from apps.org.models import Gruppo, Socio
    gruppo = Gruppo.objects.create(nome="Gruppo V2", zona=zona)
    return Socio.objects.create(
        codice_socio="900002", nome="Capo", cognome="Reparto",
        email="crp@test.it", categoria="capo", zona=zona, gruppo=gruppo,
    )


@pytest.fixture
def user_csq(db, socio_csq):
    u = User.objects.create_user(
        username="csq_user", email="csq@test.it", password="x", ruolo=Ruolo.CSQ
    )
    u.socio = socio_csq
    u.save()
    return u


@pytest.fixture
def user_crp(db, socio_crp):
    u = User.objects.create_user(
        username="crp_user", email="crp@test.it", password="x", ruolo=Ruolo.CRP
    )
    u.socio = socio_crp
    u.save()
    return u


@pytest.fixture
def edizione(db):
    from apps.editions.models import Edizione
    return Edizione.objects.create(
        anno=2098,
        scadenza_evento=timezone.now().date() + timezone.timedelta(days=30),
        scadenza_assemblea=timezone.now().date() + timezone.timedelta(days=60),
    )


@pytest.fixture
def diario(db, edizione, socio_csq, socio_crp):
    from apps.org.models import Gruppo, Reparto, Squadriglia, Zona
    zona = Zona.objects.create(nome="Zona D")
    gruppo = Gruppo.objects.create(nome="Gruppo D", zona=zona)
    reparto = Reparto.objects.create(nome="Reparto D", gruppo=gruppo)
    sq = Squadriglia.objects.create(nome="Aquile", reparto=reparto)
    return Diario.objects.create(
        edizione=edizione,
        squadriglia=sq,
        csq=socio_csq,
        crp=socio_crp,
        tipo=TipoDiario.NUOVO,
        stato=StatoDiario.IN_COMPILAZIONE,
        scadenza_riferimento=ScadenzaRiferimento.PRIMA,
    )


class TestRelazioneFinaleVisibilita:
    """La relazione finale NON deve mai essere visibile al CSQ (docs sez. 5)."""

    def test_csq_non_vede_relazione_nel_context(self, diario, user_csq, client):
        client.force_login(user_csq)
        response = client.get(f"/diari/{diario.pk}/")
        assert response.status_code == 200
        assert response.context["mostra_relazione"] is False

    def test_crp_vede_relazione_nel_context(self, diario, user_crp, client):
        client.force_login(user_crp)
        response = client.get(f"/diari/{diario.pk}/")
        assert response.status_code == 200
        assert response.context["mostra_relazione"] is True

    def test_csq_non_puo_accedere_url_relazione(self, diario, user_csq, client):
        client.force_login(user_csq)
        response = client.get(f"/diari/{diario.pk}/relazione/")
        assert response.status_code == 403

    def test_csq_non_puo_postare_relazione(self, diario, user_csq, client):
        client.force_login(user_csq)
        response = client.post(f"/diari/{diario.pk}/relazione/", {})
        assert response.status_code == 403


class TestScopingDiari:
    """Il CSQ vede solo il proprio diario; il CRP solo i diari del suo reparto."""

    def test_csq_vede_solo_il_proprio_diario(self, diario, user_csq, client):
        client.force_login(user_csq)
        response = client.get("/diari/")
        assert response.status_code == 200
        diari = list(response.context["diari"])
        assert diario in diari
        assert len(diari) == 1

    def test_csq_non_accede_a_diario_altrui(self, db, diario, edizione, user_csq, client):
        from apps.org.models import Gruppo, Reparto, Socio, Squadriglia, Zona
        zona2 = Zona.objects.create(nome="Zona Altra")
        gruppo2 = Gruppo.objects.create(nome="Gruppo Altro", zona=zona2)
        reparto2 = Reparto.objects.create(nome="Reparto Altro", gruppo=gruppo2)
        sq2 = Squadriglia.objects.create(nome="Falchi", reparto=reparto2)
        altro_csq = Socio.objects.create(
            codice_socio="900099", nome="Altro", cognome="CSQ",
            email="altro@test.it", categoria="ragazzo", zona=zona2, gruppo=gruppo2,
        )
        altro_diario = Diario.objects.create(
            edizione=edizione, squadriglia=sq2, csq=altro_csq,
            tipo=TipoDiario.NUOVO, stato=StatoDiario.IN_COMPILAZIONE,
            scadenza_riferimento=ScadenzaRiferimento.PRIMA,
        )
        client.force_login(user_csq)
        response = client.get(f"/diari/{altro_diario.pk}/")
        assert response.status_code == 403
