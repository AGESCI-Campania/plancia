# apps/accounts/tests/test_roles.py
"""Test delle regole di nomina e impersonazione (docs sez. 2)."""
import pytest

from apps.accounts.models import Ruolo, User
from apps.accounts.roles import (
    ROLE_RANK,
    can_hijack,
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
