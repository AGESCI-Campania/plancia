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


class TestEliminazioneAllegati:
    """puo_eliminare_allegati nel context del detail (docs sez. 5)."""

    def test_csq_puo_eliminare_in_compilazione(self, diario, user_csq, client):
        client.force_login(user_csq)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context["puo_eliminare_allegati"] is True

    def test_csq_puo_eliminare_in_relazione_finale(self, diario, user_csq, client):
        diario.stato = "relazione_finale"
        diario.save()
        client.force_login(user_csq)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context["puo_eliminare_allegati"] is True

    def test_crp_puo_eliminare_in_relazione_finale(self, diario, user_crp, client):
        diario.stato = "relazione_finale"
        diario.save()
        client.force_login(user_crp)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context["puo_eliminare_allegati"] is True

    def test_csq_non_puo_eliminare_dopo_invio(self, diario, user_csq, client):
        diario.stato = "inviato"
        diario.save()
        client.force_login(user_csq)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context["puo_eliminare_allegati"] is False

    def test_crp_non_puo_eliminare_dopo_invio(self, diario, user_crp, client):
        diario.stato = "inviato"
        diario.save()
        client.force_login(user_crp)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context["puo_eliminare_allegati"] is False


class TestDilazioneContext:
    """dilazione_form nel context: presente solo per staff prima dell'invio (docs sez. 4)."""

    @pytest.fixture
    def user_staff(self, db):
        import json
        from allauth.mfa.models import Authenticator
        from apps.accounts.models import Ruolo, User
        u = User.objects.create_user(
            username="staff_dil", email="staff_dil@test.it", password="x",
            ruolo=Ruolo.SEGRETERIA, is_staff=True,
        )
        Authenticator.objects.create(
            user=u, type=Authenticator.Type.TOTP,
            data=json.dumps({"secret": "AAAAAAAAAAAAAAAA"}),
        )
        return u

    def test_staff_vede_dilazione_in_compilazione(self, diario, user_staff, client):
        client.force_login(user_staff)
        resp = client.get(f"/diari/{diario.pk}/")
        assert "dilazione_form" in resp.context
        assert resp.context["dilazione_form"] is not None

    def test_staff_vede_dilazione_in_relazione_finale(self, diario, user_staff, client):
        diario.stato = "relazione_finale"
        diario.save()
        client.force_login(user_staff)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context.get("dilazione_form") is not None

    def test_staff_non_vede_dilazione_dopo_invio(self, diario, user_staff, client):
        diario.stato = "inviato"
        diario.save()
        client.force_login(user_staff)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context.get("dilazione_form") is None

    def test_csq_non_ha_dilazione(self, diario, user_csq, client):
        client.force_login(user_csq)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context.get("dilazione_form") is None


class TestNuoviCampiModello:
    """Test per i nuovi campi del modello (migrazione 0008)."""

    def test_posto_azione_chi_cosa(self, diario):
        from apps.diaries.models import Impresa, PostoAzione
        imp = Impresa.objects.create(diario=diario, numero=1)
        pa = PostoAzione.objects.create(impresa=imp, chi="Mario Rossi", cosa="Campismo")
        assert pa.chi == "Mario Rossi"
        assert pa.cosa == "Campismo"
        assert str(pa) == "Mario Rossi — Campismo"

    def test_esito_specialita_chi(self, diario):
        from apps.diaries.models import EsitoSpecialita, Impresa, TipoEsito
        imp = Impresa.objects.create(diario=diario, numero=1)
        es = EsitoSpecialita.objects.create(
            impresa=imp, tipo=TipoEsito.SPECIALITA,
            chi="Sofia Ferrari", nome="Fotografo", stato="in_cammino",
        )
        assert es.chi == "Sofia Ferrari"

    def test_membro_sq_solo_nome(self, diario):
        from apps.diaries.models import Presentazione, MembroSq
        pres = Presentazione.objects.create(diario=diario)
        m = MembroSq.objects.create(presentazione=pres, nome="Luca Bianchi", ruolo="csq")
        assert m.nome == "Luca Bianchi"
        assert m.cognome == ""
        assert str(m) == "Luca Bianchi"

    def test_anagrafica_csq_fields(self, diario):
        from apps.diaries.models import Anagrafica
        ana = Anagrafica.objects.create(
            diario=diario,
            csq_nome="Luca", csq_cognome="Bianchi",
            csq_email="luca@test.it", csq_cell="3331112222",
        )
        assert ana.csq_nome == "Luca"
        assert ana.csq_email == "luca@test.it"


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
