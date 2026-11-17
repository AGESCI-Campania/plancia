# apps/diaries/tests/test_visibilita.py
"""Test delle regole di visibilità (docs sez. 5 — tre livelli: API, queryset, funzione)."""
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
    """La relazione finale NON deve mai essere visibile al CSQ (docs sez. 5): regola e API."""

    def test_regola(self, user_csq, user_crp):
        from apps.diaries.permessi import puo_vedere_relazione

        assert puo_vedere_relazione(user_csq) is False
        assert puo_vedere_relazione(user_crp) is True

    def test_csq_non_legge_ne_scrive_la_relazione(self, diario, user_csq, client):
        client.force_login(user_csq)
        url = f"/api/v1/diari/{diario.pk}/relazione-finale"
        assert client.get(url).status_code == 403
        r = client.put(url, data='{"version": 0, "data": {}}', content_type="application/json")
        assert r.status_code == 403

    def test_crp_legge_la_relazione(self, diario, user_crp, client):
        client.force_login(user_crp)
        assert client.get(f"/api/v1/diari/{diario.pk}/relazione-finale").status_code == 200


class TestEliminazioneAllegati:
    """`permessi.puo_eliminare_allegati` (docs sez. 5): fino all'invio del diario."""

    @pytest.mark.parametrize("stato,ruolo,atteso", [
        (StatoDiario.IN_COMPILAZIONE, "csq", True),
        (StatoDiario.RELAZIONE_FINALE, "csq", True),
        (StatoDiario.RELAZIONE_FINALE, "crp", True),
        (StatoDiario.INVIATO, "csq", False),
        (StatoDiario.INVIATO, "crp", False),
    ])
    def test_regola(self, diario, user_csq, user_crp, stato, ruolo, atteso):
        from apps.diaries.permessi import puo_eliminare_allegati

        diario.stato = stato
        diario.save()
        utente = user_csq if ruolo == "csq" else user_crp
        assert puo_eliminare_allegati(utente, diario) is atteso


class TestDilazione:
    """`permessi.puo_concedere_dilazione`: solo staff, prima dell'invio (docs sez. 4)."""

    @pytest.fixture
    def user_staff(self, db):
        return User.objects.create_user(
            username="staff_dil", email="staff_dil@test.it", password="x",
            ruolo=Ruolo.SEGRETERIA, is_staff=True,
        )

    @pytest.mark.parametrize("stato,atteso", [
        (StatoDiario.IN_COMPILAZIONE, True),
        (StatoDiario.RELAZIONE_FINALE, True),
        (StatoDiario.INVIATO, False),
    ])
    def test_staff(self, diario, user_staff, stato, atteso):
        from apps.diaries.permessi import puo_concedere_dilazione

        diario.stato = stato
        diario.save()
        assert puo_concedere_dilazione(user_staff, diario) is atteso

    def test_csq_mai(self, diario, user_csq):
        from apps.diaries.permessi import puo_concedere_dilazione

        assert puo_concedere_dilazione(user_csq, diario) is False


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
        from apps.diaries.models import MembroSq, Presentazione
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
    """Il CSQ vede solo il proprio diario (elenco e dettaglio dell'API)."""

    def test_csq_vede_solo_il_proprio_diario(self, diario, user_csq, client):
        client.force_login(user_csq)
        response = client.get("/api/v1/diari")
        assert response.status_code == 200
        assert [d["id"] for d in response.json()["items"]] == [diario.pk]

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
        response = client.get(f"/api/v1/diari/{altro_diario.pk}")
        assert response.status_code in (403, 404)


class TestDiariVisibili:
    """Test diretti su apps.diaries.visibility.diari_visibili()."""

    def test_staff_vede_tutti(self, db, diario, user_crp):
        from apps.accounts.models import Ruolo
        user_crp.ruolo = Ruolo.SEGRETERIA
        user_crp.save()
        from apps.diaries.visibility import diari_visibili
        qs = diari_visibili(user_crp)
        assert diario in qs

    def test_csq_vede_solo_il_proprio(self, db, diario, user_csq):
        from apps.diaries.visibility import diari_visibili
        qs = diari_visibili(user_csq)
        assert list(qs) == [diario]

    def test_csq_non_vede_diari_altrui(self, db, diario, user_csq, edizione):
        from apps.diaries.visibility import diari_visibili
        from apps.org.models import Gruppo, Reparto, Socio, Squadriglia, Zona
        zona2 = Zona.objects.create(nome="Zona Altra TV")
        gruppo2 = Gruppo.objects.create(nome="Gruppo Altro TV", zona=zona2)
        reparto2 = Reparto.objects.create(nome="Reparto Altro TV", gruppo=gruppo2)
        sq2 = Squadriglia.objects.create(nome="Volpi", reparto=reparto2)
        csq2 = Socio.objects.create(
            codice_socio="911001", nome="Altro", cognome="Csq",
            email="altro_csq@test.it", categoria="ragazzo", zona=zona2, gruppo=gruppo2,
        )
        Diario.objects.create(
            edizione=edizione, squadriglia=sq2, csq=csq2,
            tipo=TipoDiario.NUOVO, stato=StatoDiario.IN_COMPILAZIONE,
            scadenza_riferimento=ScadenzaRiferimento.PRIMA,
        )
        qs = diari_visibili(user_csq)
        assert qs.count() == 1
        assert qs.first().csq == user_csq.socio

    def test_crp_vede_solo_propri_diari(self, db, diario, user_crp):
        from apps.diaries.visibility import diari_visibili
        qs = diari_visibili(user_crp)
        assert diario in qs
        for d in qs:
            assert d.crp == user_crp.socio

    def test_filtro_edizione(self, db, diario, user_crp, edizione):
        from apps.diaries.visibility import diari_visibili
        from apps.editions.models import Edizione
        Edizione.objects.create(anno=2099)  # un'altra edizione, da escludere
        qs = diari_visibili(user_crp, edizione=edizione)
        assert diario in qs
        assert all(d.edizione_id == edizione.pk for d in qs)

    def test_pgv_vede_solo_assegnati(self, db, diario, user_csq, edizione):
        from apps.accounts.models import Ruolo, User
        from apps.diaries.visibility import diari_visibili
        from apps.evaluations.models import AssegnazionePGV, Valutazione

        pgv = User.objects.create_user(
            username="pgv_tv", email="pgv_tv@test.it", password="x", ruolo=Ruolo.PGV
        )
        val = Valutazione.objects.create(diario=diario)
        AssegnazionePGV.objects.create(pgv=pgv, valutazione=val)

        qs = diari_visibili(pgv)
        assert diario in qs

    def test_ruolo_sconosciuto_vede_niente(self, db, diario):
        from apps.accounts.models import User
        from apps.diaries.visibility import diari_visibili
        u = User.objects.create_user(
            username="nessuno_tv", email="nessuno_tv@test.it", password="x"
        )
        qs = diari_visibili(u)
        assert qs.count() == 0
