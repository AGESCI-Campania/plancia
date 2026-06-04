# apps/diaries/tests/conftest.py
"""Fixture condivise per i test del modulo diaries."""
import pytest
from django.utils import timezone

from apps.accounts.models import Ruolo, User
from apps.diaries.models import Diario, ScadenzaRiferimento, StatoDiario, TipoDiario


# ---------------------------------------------------------------------------
# Org fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def zona(db):
    from apps.org.models import Zona
    return Zona.objects.create(nome="Zona Test Diaries")


@pytest.fixture
def gruppo(db, zona):
    from apps.org.models import Gruppo
    return Gruppo.objects.create(nome="Gruppo Test Diaries", zona=zona)


@pytest.fixture
def reparto(db, gruppo):
    from apps.org.models import Reparto
    return Reparto.objects.create(nome="Reparto Test Diaries", gruppo=gruppo)


@pytest.fixture
def squadriglia(db, reparto):
    from apps.org.models import Squadriglia
    return Squadriglia.objects.create(nome="Tigri", reparto=reparto)


@pytest.fixture
def socio_csq(db, zona, gruppo):
    from apps.org.models import Socio
    return Socio.objects.create(
        codice_socio="800001", nome="Primo", cognome="CSQ",
        email="csq1@test.it", categoria="ragazzo", zona=zona, gruppo=gruppo,
    )


@pytest.fixture
def socio_csq_alt(db, zona, gruppo):
    """Secondo Capo Squadriglia per i test di sostituzione."""
    from apps.org.models import Socio
    return Socio.objects.create(
        codice_socio="800002", nome="Secondo", cognome="CSQ",
        email="csq2@test.it", categoria="ragazzo", zona=zona, gruppo=gruppo,
    )


@pytest.fixture
def socio_crp(db, zona, gruppo):
    from apps.org.models import Socio
    return Socio.objects.create(
        codice_socio="800003", nome="Primo", cognome="CRP",
        email="crp1@test.it", categoria="capo", zona=zona, gruppo=gruppo,
    )


@pytest.fixture
def socio_crp_alt(db, zona, gruppo):
    """Secondo Capo Reparto per i test di sostituzione."""
    from apps.org.models import Socio
    return Socio.objects.create(
        codice_socio="800004", nome="Secondo", cognome="CRP",
        email="crp2@test.it", categoria="capo", zona=zona, gruppo=gruppo,
    )


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_csq(db, socio_csq):
    u = User.objects.create_user(
        username="csq1_user", email="csq1@test.it", password="testpass123",
        ruolo=Ruolo.CSQ,
    )
    u.socio = socio_csq
    u.save()
    return u


@pytest.fixture
def user_crp(db, socio_crp):
    u = User.objects.create_user(
        username="crp1_user", email="crp1@test.it", password="testpass123",
        ruolo=Ruolo.CRP,
    )
    u.socio = socio_crp
    u.save()
    return u


@pytest.fixture
def user_admin(db):
    import json
    from allauth.mfa.models import Authenticator

    u = User.objects.create_superuser(
        username="admin_test", email="admin@test.it", password="testpass123",
    )
    u.refresh_from_db()
    # Il superuser richiede MFA — aggiungi TOTP per non essere bloccato dal middleware
    Authenticator.objects.create(
        user=u,
        type=Authenticator.Type.TOTP,
        data=json.dumps({"secret": "AAAAAAAAAAAAAAAA"}),
    )
    return u


# ---------------------------------------------------------------------------
# Edition & Diary
# ---------------------------------------------------------------------------

@pytest.fixture
def edizione(db):
    from apps.editions.models import Edizione
    return Edizione.objects.create(
        anno=2097,
        scadenza_evento=timezone.now().date() + timezone.timedelta(days=30),
        scadenza_assemblea=timezone.now().date() + timezone.timedelta(days=60),
    )


@pytest.fixture
def diario(db, edizione, squadriglia, socio_csq, socio_crp):
    return Diario.objects.create(
        edizione=edizione,
        squadriglia=squadriglia,
        csq=socio_csq,
        crp=socio_crp,
        tipo=TipoDiario.NUOVO,
        stato=StatoDiario.IN_COMPILAZIONE,
        scadenza_riferimento=ScadenzaRiferimento.PRIMA,
    )
