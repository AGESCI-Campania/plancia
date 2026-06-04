# apps/diaries/tests/test_fsm.py
"""Test della FSM del Diario (docs sez. 6)."""
import pytest
from django.utils import timezone

from apps.diaries.models import Diario, ScadenzaRiferimento, StatoDiario, TipoDiario


@pytest.fixture
def edizione(db):
    from apps.editions.models import Edizione

    return Edizione.objects.create(
        anno=2099,
        scadenza_evento=timezone.now().date() + timezone.timedelta(days=30),
        scadenza_assemblea=timezone.now().date() + timezone.timedelta(days=60),
    )


@pytest.fixture
def squadriglia(db):
    from apps.org.models import Gruppo, Reparto, Squadriglia, Zona

    zona = Zona.objects.create(nome="Zona FSM")
    gruppo = Gruppo.objects.create(nome="Gruppo FSM", zona=zona)
    reparto = Reparto.objects.create(nome="Reparto FSM", gruppo=gruppo)
    return Squadriglia.objects.create(nome="Tigri", reparto=reparto)


@pytest.fixture
def diario(db, edizione, squadriglia):
    return Diario.objects.create(
        edizione=edizione,
        squadriglia=squadriglia,
        tipo=TipoDiario.NUOVO,
        stato=StatoDiario.IN_COMPILAZIONE,
        scadenza_riferimento=ScadenzaRiferimento.PRIMA,
    )


class TestTransizioni:
    def test_csq_invia_da_in_compilazione(self, diario):
        """IN_COMPILAZIONE → RELAZIONE_FINALE via csq_invia()."""
        diario.csq_invia()
        diario.refresh_from_db()
        assert diario.stato == StatoDiario.RELAZIONE_FINALE

    def test_crp_invia_da_relazione_finale(self, diario):
        """RELAZIONE_FINALE → INVIATO via invia()."""
        diario.stato = StatoDiario.RELAZIONE_FINALE
        diario.save()
        diario.invia()
        diario.refresh_from_db()
        assert diario.stato == StatoDiario.INVIATO
        assert diario.inviato_at is not None

    def test_invia_non_ammesso_da_in_compilazione(self, diario):
        """invia() non è ammessa direttamente da IN_COMPILAZIONE."""
        with pytest.raises(ValueError):
            diario.invia()

    def test_invia_solo_da_relazione_finale(self, diario):
        """invia() lancia ValueError da stati diversi da RELAZIONE_FINALE."""
        diario.stato = StatoDiario.INVIATO
        diario.save()
        with pytest.raises(ValueError):
            diario.invia()

    def test_avvia_valutazione(self, diario):
        diario.stato = StatoDiario.INVIATO
        diario.save()
        diario.avvia_valutazione()
        assert diario.stato == StatoDiario.IN_VALUTAZIONE

    def test_approva_direttamente(self, diario):
        diario.stato = StatoDiario.IN_VALUTAZIONE
        diario.save()
        diario.approva()
        assert diario.stato == StatoDiario.APPROVATO

    def test_respingi_direttamente(self, diario):
        diario.stato = StatoDiario.IN_VALUTAZIONE
        diario.save()
        diario.respingi()
        assert diario.stato == StatoDiario.NON_APPROVATO

    def test_richiedi_info(self, diario):
        diario.stato = StatoDiario.IN_VALUTAZIONE
        diario.save()
        diario.richiedi_info()
        assert diario.stato == StatoDiario.MAGGIORI_INFO

    def test_proponi_va_in_revisione(self, diario):
        diario.stato = StatoDiario.IN_VALUTAZIONE
        diario.save()
        diario.proponi(StatoDiario.APPROVATO)
        assert diario.stato == StatoDiario.IN_REVISIONE

    def test_proponi_maggiori_info_non_ammessa(self, diario):
        diario.stato = StatoDiario.IN_VALUTAZIONE
        diario.save()
        with pytest.raises(ValueError):
            diario.proponi(StatoDiario.MAGGIORI_INFO)

    def test_conferma_in_revisione(self, diario):
        diario.stato = StatoDiario.IN_REVISIONE
        diario.save()
        diario.approva()
        assert diario.stato == StatoDiario.APPROVATO

    def test_rigetta_proposta_torna_in_valutazione(self, diario):
        diario.stato = StatoDiario.IN_REVISIONE
        diario.save()
        diario.rigetta_proposta()
        assert diario.stato == StatoDiario.IN_VALUTAZIONE

    def test_transizione_non_ammessa_solleva_errore(self, diario):
        diario.stato = StatoDiario.APPROVATO
        diario.save()
        with pytest.raises(ValueError):
            diario._transita(StatoDiario.INVIATO)


class TestRiapertura:
    def test_riapertura_ammessa_su_prima_scadenza(self, diario):
        diario.stato = StatoDiario.NON_APPROVATO
        diario.scadenza_riferimento = ScadenzaRiferimento.PRIMA
        diario.save()
        assert diario.puo_essere_riaperto() is True
        diario.riapri()
        assert diario.stato == StatoDiario.IN_COMPILAZIONE

    def test_riapertura_negata_su_seconda_scadenza(self, diario):
        diario.stato = StatoDiario.NON_APPROVATO
        diario.scadenza_riferimento = ScadenzaRiferimento.SECONDA
        diario.save()
        assert diario.puo_essere_riaperto() is False
        with pytest.raises(ValueError):
            diario.riapri()

    def test_riapertura_negata_se_seconda_scadenza_passata(self, diario, edizione):
        edizione.scadenza_assemblea = timezone.now().date() - timezone.timedelta(days=1)
        edizione.save()
        diario.stato = StatoDiario.MAGGIORI_INFO
        diario.scadenza_riferimento = ScadenzaRiferimento.PRIMA
        diario.save()
        assert diario.puo_essere_riaperto() is False
