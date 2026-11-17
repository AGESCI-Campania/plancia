# apps/diaries/tests/test_cambio_referenti.py
"""Cambio Capo Reparto in blocco (`service.cambia_crp_reparto`, docs sez. 4).

Permessi e validazioni di cambio CSQ/CRP del singolo diario sono coperti dai test API
(`apps/api/tests/test_diari.py`, sezione "Cambio referenti").
"""
import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.diaries import service
from apps.diaries.models import Diario, StatoDiario


class TestCambiaCrpReparto:
    def test_aggiorna_diari_non_inviati(self, diario, user_admin, socio_crp_alt):
        nuovo, n = service.cambia_crp_reparto(diario.squadriglia.reparto, socio_crp_alt.pk, user_admin)
        assert (nuovo, n) == (socio_crp_alt, 1)
        diario.refresh_from_db()
        assert diario.crp == socio_crp_alt

    def test_non_tocca_diari_inviati(
        self, db, edizione, squadriglia, socio_csq, socio_crp, socio_crp_alt, user_admin
    ):
        inviato = Diario.objects.create(
            edizione=edizione, squadriglia=squadriglia, csq=socio_csq, crp=socio_crp,
            stato=StatoDiario.INVIATO,
        )
        service.cambia_crp_reparto(squadriglia.reparto, socio_crp_alt.pk, user_admin)
        inviato.refresh_from_db()
        assert inviato.crp == socio_crp

    def test_aggiorna_piu_diari_dello_stesso_reparto(
        self, db, edizione, reparto, socio_csq, socio_csq_alt, socio_crp, socio_crp_alt, user_admin
    ):
        from apps.org.models import Squadriglia

        d1 = Diario.objects.create(
            edizione=edizione, squadriglia=Squadriglia.objects.create(nome="Leoni", reparto=reparto),
            csq=socio_csq, crp=socio_crp, stato=StatoDiario.IN_COMPILAZIONE,
        )
        d2 = Diario.objects.create(
            edizione=edizione, squadriglia=Squadriglia.objects.create(nome="Lupi", reparto=reparto),
            csq=socio_csq_alt, crp=socio_crp, stato=StatoDiario.RELAZIONE_FINALE,
        )
        _, n = service.cambia_crp_reparto(reparto, socio_crp_alt.pk, user_admin)
        assert n == 2
        d1.refresh_from_db()
        d2.refresh_from_db()
        assert d1.crp == d2.crp == socio_crp_alt

    def test_reparto_senza_diari_modificabili(self, db, reparto):
        assert list(service.diari_cambio_crp_reparto(reparto)) == []

    def test_crp_non_puo(self, diario, user_crp, socio_crp_alt):
        with pytest.raises(PermissionDenied):
            service.cambia_crp_reparto(diario.squadriglia.reparto, socio_crp_alt.pk, user_crp)

    def test_ragazzo_rifiutato_come_crp(self, diario, user_admin, socio_csq_alt):
        with pytest.raises(ValidationError):
            service.cambia_crp_reparto(diario.squadriglia.reparto, socio_csq_alt.pk, user_admin)
