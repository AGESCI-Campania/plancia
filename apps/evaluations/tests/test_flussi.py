# apps/evaluations/tests/test_flussi.py
"""Test dei due flussi di valutazione: diretto (Incaricato) e via Pattuglia GV."""
import pytest
from django.utils import timezone

from apps.accounts.models import Ruolo, User
from apps.diaries.models import Diario, ScadenzaRiferimento, StatoDiario, TipoDiario
from apps.evaluations.models import EsitoValutazione, StatoValutazione, Valutazione


def _setup_diario_incaricato():
    """Helper: crea dati minimi per testare il flusso di valutazione."""
    from apps.editions.models import Edizione
    from apps.org.models import Gruppo, Reparto, Squadriglia, Zona

    edizione = Edizione.objects.create(
        anno=2099,
        scadenza_evento=timezone.now().date() + timezone.timedelta(days=30),
        scadenza_assemblea=timezone.now().date() + timezone.timedelta(days=60),
    )
    zona = Zona.objects.create(nome="Zona Val")
    gruppo = Gruppo.objects.create(nome="Gruppo Val", zona=zona)
    reparto = Reparto.objects.create(nome="Reparto Val", gruppo=gruppo)
    squadriglia = Squadriglia.objects.create(nome="Aquile", reparto=reparto)
    diario = Diario.objects.create(
        edizione=edizione,
        squadriglia=squadriglia,
        tipo=TipoDiario.NUOVO,
        stato=StatoDiario.INVIATO,
        scadenza_riferimento=ScadenzaRiferimento.PRIMA,
    )
    incaricato = User.objects.create_user(
        username="incaricato", email="incaricato@test.it", password="pass",
        ruolo=Ruolo.INCARICATO_EG,
    )
    return diario, incaricato


class TestFlussoDirectoModello:
    """Logica del flusso diretto a livello di modello (nessun client HTTP)."""

    def test_valuta_direttamente_da_inviato(self, db):
        """valuta_direttamente con auto-avvia_valutazione transita il diario ad APPROVATO."""
        diario, incaricato = _setup_diario_incaricato()
        val, _ = Valutazione.objects.get_or_create(diario=diario)
        diario.avvia_valutazione()
        val.valuta_direttamente(incaricato, EsitoValutazione.APPROVATA, "ottimo lavoro")

        diario.refresh_from_db()
        val.refresh_from_db()
        assert val.esito == EsitoValutazione.APPROVATA
        assert val.stato == StatoValutazione.CONFERMATA
        assert diario.stato == StatoDiario.APPROVATO

    def test_valuta_direttamente_maggiori_info(self, db):
        """MAGGIORI_INFO transita il diario in stato MAGGIORI_INFO."""
        diario, incaricato = _setup_diario_incaricato()
        val, _ = Valutazione.objects.get_or_create(diario=diario)
        diario.avvia_valutazione()
        val.valuta_direttamente(incaricato, EsitoValutazione.MAGGIORI_INFO, "servono dettagli")

        diario.refresh_from_db()
        assert diario.stato == StatoDiario.MAGGIORI_INFO

    def test_valuta_direttamente_ignora_proposta_pgv(self, db):
        """L'Incaricato può sovrascrivere una proposta PGV in IN_REVISIONE."""
        diario, incaricato = _setup_diario_incaricato()
        diario.stato = StatoDiario.IN_REVISIONE
        diario.save()
        val = Valutazione.objects.create(
            diario=diario,
            stato=StatoValutazione.IN_REVISIONE,
            proposta_esito=EsitoValutazione.APPROVATA,
        )
        val.valuta_direttamente(incaricato, EsitoValutazione.NON_APPROVATA, "override")

        val.refresh_from_db()
        diario.refresh_from_db()
        assert val.esito == EsitoValutazione.NON_APPROVATA
        assert val.stato == StatoValutazione.CONFERMATA
        assert diario.stato == StatoDiario.NON_APPROVATO


