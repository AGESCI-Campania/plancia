"""`manage.py popola_demo`: crea i dati dimostrativi ed è ripetibile senza duplicati."""
import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import Nomina, User
from apps.diaries.models import Allegato, Diario
from apps.editions.models import Edizione
from apps.evaluations.models import Valutazione
from apps.helpdesk.models import Ticket
from apps.imports.models import LogImportazione
from apps.notifications.models import Invito

pytestmark = pytest.mark.django_db

PASSWORD = "Demo-Prova-2027"


@pytest.fixture(autouse=True)
def _media_temporanei(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _popola(*argomenti: str) -> None:
    call_command("popola_demo", "--password", PASSWORD, "--anno", "2099", "--consenti-senza-debug",
                 *argomenti)


def _conteggi() -> dict[str, int]:
    modelli = (User, Nomina, Diario, Allegato, Valutazione, Invito, Ticket, LogImportazione)
    return {m.__name__: m.objects.count() for m in modelli}


def test_crea_dati_per_ogni_ruolo():
    _popola()
    edizione = Edizione.objects.get(anno=2099)
    stati = set(edizione.diari.values_list("stato", flat=True))
    assert {"non_iniziato", "in_compilazione", "relazione_finale", "inviato", "in_valutazione",
            "in_revisione", "approvato", "maggiori_info"} <= stati
    for email in ("admin", "segreteria", "incaricato", "pgv", "crp", "csq"):
        utente = User.objects.get(email=f"{email}@example.org")
        assert utente.check_password(PASSWORD)
    csq = User.objects.get(email="csq@example.org")
    assert csq.username == csq.socio.codice_socio  # accesso con il codice socio
    from allauth.mfa.models import Authenticator
    staff = Authenticator.objects.filter(type=Authenticator.Type.TOTP).values_list("user__email", flat=True)
    assert set(staff) == {"admin@example.org", "segreteria@example.org", "incaricato@example.org"}
    assert Valutazione.objects.filter(diario__edizione=edizione).exists()
    assert Allegato.objects.filter(diario__edizione=edizione).exists()
    assert Ticket.objects.filter(diario__edizione=edizione).count() == 2
    assert LogImportazione.objects.filter(edizione=edizione).exists()


def test_ripetibile_e_ricrea():
    _popola()
    prima = _conteggi()
    _popola()
    assert _conteggi() == prima
    _popola("--ricrea")
    assert _conteggi() == prima
    assert Ticket.objects.filter(diario__isnull=True).count() == 0


def test_senza_password_o_senza_debug(settings):
    with pytest.raises(CommandError):
        call_command("popola_demo", "--password", "corta", "--consenti-senza-debug")
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("popola_demo", "--password", PASSWORD)
