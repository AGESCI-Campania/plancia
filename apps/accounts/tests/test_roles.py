# apps/accounts/tests/test_roles.py
"""Test delle regole di nomina e impersonazione (docs sez. 2)."""

import pytest

from apps.accounts.models import Nomina, Ruolo
from apps.accounts.roles import (
    ROLE_RANK,
    _rango_massimo,
    categoria_compatibile,
    puo_impersonare,
    puo_nominare,
)


class TestNomina:
    def test_admin_puo_nominare_segreteria(self):
        assert puo_nominare(Ruolo.ADMIN, Ruolo.SEGRETERIA) is True

    def test_segreteria_non_puo_nominare_segreteria(self):
        assert puo_nominare(Ruolo.SEGRETERIA, Ruolo.SEGRETERIA) is False

    def test_iabr_puo_nominare_pgv(self):
        assert puo_nominare(Ruolo.INCARICATO_EG, Ruolo.PGV) is True

    def test_crp_non_puo_nominare_nessuno(self):
        for ruolo in Ruolo:
            assert puo_nominare(Ruolo.CRP, ruolo) is False

    def test_categoria_compatibile_csq_ragazzo(self):
        assert categoria_compatibile(Ruolo.CSQ, "ragazzo") is True

    def test_categoria_incompatibile_csq_capo(self):
        assert categoria_compatibile(Ruolo.CSQ, "capo") is False

    def test_categoria_compatibile_crp_capo(self):
        assert categoria_compatibile(Ruolo.CRP, "capo") is True

    def test_admin_nessun_vincolo_categoria(self):
        assert categoria_compatibile(Ruolo.ADMIN, None) is True
        assert categoria_compatibile(Ruolo.ADMIN, "capo") is True
        assert categoria_compatibile(Ruolo.ADMIN, "ragazzo") is True


class _FakeUser:
    """Stub utente per test senza DB."""
    def __init__(self, ruolo, pk=None):
        self.ruolo = ruolo
        self.pk = pk or id(self)


class TestImpersonazione:
    def test_admin_puo_impersonare_csq(self):
        assert puo_impersonare(_FakeUser(Ruolo.ADMIN), _FakeUser(Ruolo.CSQ)) is True

    def test_segreteria_puo_impersonare_csq(self):
        assert puo_impersonare(_FakeUser(Ruolo.SEGRETERIA), _FakeUser(Ruolo.CSQ)) is True

    def test_segreteria_non_puo_impersonare_admin(self):
        assert puo_impersonare(_FakeUser(Ruolo.SEGRETERIA), _FakeUser(Ruolo.ADMIN)) is False

    def test_csq_non_puo_impersonare_nessuno(self):
        assert puo_impersonare(_FakeUser(Ruolo.CSQ), _FakeUser(Ruolo.ADMIN)) is False

    def test_nessuno_impersona_se_stesso(self):
        u = _FakeUser(Ruolo.ADMIN, pk=1)
        assert puo_impersonare(u, u) is False

    def test_ranghi_ordinati_correttamente(self):
        assert ROLE_RANK[Ruolo.ADMIN] > ROLE_RANK[Ruolo.SEGRETERIA]
        assert ROLE_RANK[Ruolo.SEGRETERIA] > ROLE_RANK[Ruolo.INCARICATO_EG]
        assert ROLE_RANK[Ruolo.INCARICATO_EG] > ROLE_RANK[Ruolo.PGV]
        assert ROLE_RANK[Ruolo.PGV] > ROLE_RANK[Ruolo.CRP]
        assert ROLE_RANK[Ruolo.CRP] > ROLE_RANK[Ruolo.CSQ]

    def test_segreteria_non_puo_impersonare_utente_con_nomina_admin(self):
        """Anche se l'utente ha ruolo attivo CSQ, la Segreteria non può impersonarlo
        se ha una nomina Admin attiva (il rango massimo conta)."""
        class _FakeUserMultiRuolo:
            def __init__(self, ruolo_attivo, ruoli_extra):
                self.ruolo = ruolo_attivo
                self.pk = id(self)
                self._ruoli_attivi = [ruolo_attivo] + ruoli_extra

            @property
            def ruoli_attivi(self):
                return self._ruoli_attivi

        target = _FakeUserMultiRuolo(Ruolo.CSQ, [Ruolo.ADMIN])
        segreteria = _FakeUser(Ruolo.SEGRETERIA)
        assert puo_impersonare(segreteria, target) is False

    def test_rango_massimo_con_ruoli_multipli(self):
        class _FakeUserMultiRuolo:
            def __init__(self, ruoli):
                self.ruolo = ruoli[0]
                self.pk = id(self)

            @property
            def ruoli_attivi(self):
                return [Ruolo.CSQ, Ruolo.PGV]

        u = _FakeUserMultiRuolo([Ruolo.CSQ])
        assert _rango_massimo(u) == ROLE_RANK[Ruolo.PGV]


@pytest.mark.django_db
class TestNominaMultiRuolo:
    def _crea_zona_gruppo(self):
        from apps.org.models import Gruppo, Zona
        zona = Zona.objects.create(nome="TestZona")
        gruppo = Gruppo.objects.create(nome="TestGruppo", zona=zona)
        return zona, gruppo

    def test_primo_ruolo_attiva_user_ruolo(self, django_user_model):
        """Al primo ruolo assegnato, User.ruolo viene aggiornato."""
        from apps.accounts.roles import nomina as service_nomina
        from apps.org.models import Socio

        zona, gruppo = self._crea_zona_gruppo()
        socio_capo = Socio.objects.create(
            codice_socio="10001", nome="Mario", cognome="Rossi",
            gruppo=gruppo, zona=zona, categoria="capo"
        )
        admin = django_user_model.objects.create_superuser(
            username="admin_t1", email="admin_t1@test.it", password="x"
        )
        admin.refresh_from_db()
        utente = django_user_model.objects.create_user(
            username="u1", email="u1@test.it", password="x"
        )
        utente.socio = socio_capo
        utente.save()
        service_nomina(admin, utente, Ruolo.CRP)
        utente.refresh_from_db()
        assert utente.ruolo == Ruolo.CRP

    def test_secondo_ruolo_non_cambia_ruolo_attivo(self, django_user_model):
        """Se l'utente ha già un ruolo attivo, la seconda nomina non lo cambia."""
        from apps.accounts.roles import nomina as service_nomina
        from apps.org.models import Socio

        zona, gruppo = self._crea_zona_gruppo()
        socio_capo = Socio.objects.create(
            codice_socio="10002", nome="Luigi", cognome="Verdi",
            gruppo=gruppo, zona=zona, categoria="capo"
        )
        admin = django_user_model.objects.create_superuser(
            username="admin_t2", email="admin_t2@test.it", password="x"
        )
        admin.refresh_from_db()
        utente = django_user_model.objects.create_user(
            username="u2", email="u2@test.it", password="x", ruolo=Ruolo.CRP
        )
        utente.socio = socio_capo
        utente.save()
        Nomina.objects.create(utente=utente, ruolo=Ruolo.CRP, nominato_da=admin)
        service_nomina(admin, utente, Ruolo.PGV)
        utente.refresh_from_db()
        assert utente.ruolo == Ruolo.CRP

    def test_nomina_staff_diretto_crea_utente_senza_socio(self, django_user_model):
        """nomina_staff_diretto crea User + Nomina senza richiedere un Socio."""
        from apps.accounts.roles import nomina_staff_diretto

        admin = django_user_model.objects.create_superuser(
            username="admin_staff", email="admin_staff@test.it", password="x"
        )
        admin.refresh_from_db()
        utente, nomina_obj, creato = nomina_staff_diretto(
            admin, "seg1@test.it", "Luisa", "Bianchi", Ruolo.SEGRETERIA
        )
        assert creato is True
        assert utente.email == "seg1@test.it"
        assert utente.ruolo == Ruolo.SEGRETERIA
        assert not utente.has_usable_password()
        assert nomina_obj.ruolo == Ruolo.SEGRETERIA
        assert nomina_obj.socio is None

    def test_nomina_staff_diretto_errore_permesso(self, django_user_model):
        """La Segreteria non può creare un Admin."""
        from apps.accounts.roles import nomina_staff_diretto

        seg = django_user_model.objects.create_user(
            username="seg_x", email="seg_x@test.it", password="x", ruolo=Ruolo.SEGRETERIA
        )
        with pytest.raises(PermissionError):
            nomina_staff_diretto(seg, "nuovoadmin@test.it", "A", "B", Ruolo.ADMIN)

    def test_csq_esclusivo_nella_stessa_edizione(self, django_user_model):
        """CSQ e altri ruoli non possono coesistere nella stessa edizione."""
        from apps.accounts.roles import nomina as service_nomina
        from apps.editions.models import Edizione
        from apps.org.models import Socio

        zona, gruppo = self._crea_zona_gruppo()
        admin = django_user_model.objects.create_superuser(
            username="admin_t3", email="admin_t3@test.it", password="x"
        )
        admin.refresh_from_db()
        edizione = Edizione.objects.create(anno=2099, stato="aperta")

        socio_capo = Socio.objects.create(
            codice_socio="10004", nome="Pino", cognome="Neri",
            gruppo=gruppo, zona=zona, categoria="capo"
        )
        utente_capo = django_user_model.objects.create_user(
            username="u4", email="u4@test.it", password="x"
        )
        utente_capo.socio = socio_capo
        utente_capo.save()
        service_nomina(admin, utente_capo, Ruolo.CRP, edizione=edizione)
        with pytest.raises(ValueError, match="CSQ"):
            service_nomina(admin, utente_capo, Ruolo.CSQ, edizione=edizione)
