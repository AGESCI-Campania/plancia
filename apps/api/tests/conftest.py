"""Fixture condivise dai test dell'API: un utente per ruolo, organizzazione, edizione, diario.

Uso tipico:

    def test_qualcosa(client_di, diario):
        r = client_di("crp").get(f"/api/v1/diari/{diario.pk}")

Gli utenti di staff hanno la MFA (TOTP) configurata, come richiesto dal loro ruolo.
`client_di(ruolo)` restituisce un `django.test.Client` autenticato con l'utente di quel ruolo
(cookie di sessione, come la SPA); `"estraneo"` è un CSQ di un'altra squadriglia, `"anonimo"`
un client non autenticato. Gli utenti hanno la `Nomina` corrispondente al ruolo attivo.
"""
from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Nomina, Ruolo, User
from apps.diaries.models import Diario, ScadenzaRiferimento, StatoDiario, TipoDiario

RUOLI_TEST = ("admin", "segreteria", "incaricato_eg", "pgv", "crp", "csq", "estraneo")


@pytest.fixture
def org(db):
    """Zona → Gruppo → Reparto → due squadriglie (Tigri, Aquile)."""
    from apps.org.models import Gruppo, Reparto, Squadriglia, Zona

    zona = Zona.objects.create(nome="Zona API")
    gruppo = Gruppo.objects.create(nome="Gruppo API", zona=zona)
    reparto = Reparto.objects.create(nome="Reparto API", gruppo=gruppo)
    return {
        "zona": zona,
        "gruppo": gruppo,
        "reparto": reparto,
        "squadriglia": Squadriglia.objects.create(nome="Tigri", reparto=reparto),
        "squadriglia_altra": Squadriglia.objects.create(nome="Aquile", reparto=reparto),
    }


def _socio(org, codice: str, categoria: str, nome: str):
    from apps.org.models import Socio

    return Socio.objects.create(
        codice_socio=codice, nome=nome, cognome="Test", email=f"{nome.lower()}@test.it",
        categoria=categoria, zona=org["zona"], gruppo=org["gruppo"],
    )


@pytest.fixture
def utenti(db, org) -> dict[str, User]:
    """Un utente per ciascun ruolo di `RUOLI_TEST`, con Socio dove il ruolo lo richiede."""
    soci = {
        "segreteria": _socio(org, "700001", "capo", "Segreteria"),
        "incaricato_eg": _socio(org, "700002", "capo", "Incaricato"),
        "pgv": _socio(org, "700003", "capo", "Pgv"),
        "crp": _socio(org, "700004", "capo", "Crp"),
        "csq": _socio(org, "700005", "ragazzo", "Csq"),
        "estraneo": _socio(org, "700006", "ragazzo", "Estraneo"),
    }
    ruolo_di = {"estraneo": Ruolo.CSQ}
    risultato: dict[str, User] = {}
    for chiave in RUOLI_TEST:
        ruolo = ruolo_di.get(chiave, chiave)
        email = f"{chiave}@test.it"
        if chiave == "admin":
            u = User.objects.create_superuser(username=email, email=email, password="pw-test-123")
            u.refresh_from_db()  # il signal ensure_superuser_ruolo corregge il ruolo a DB
        else:
            u = User.objects.create_user(
                username=email, email=email, password="pw-test-123", ruolo=ruolo,
                socio=soci.get(chiave),
            )
        Nomina.objects.get_or_create(utente=u, ruolo=u.ruolo, defaults={"socio": u.socio})
        if chiave in RUOLI_CON_MFA:
            _attiva_totp(u)
        risultato[chiave] = u
    return risultato


# Ruoli con MFA obbligatoria: in produzione non usano l'API senza averla configurata.
RUOLI_CON_MFA = ("admin", "segreteria", "incaricato_eg")


def _attiva_totp(utente: User) -> None:
    from allauth.mfa.models import Authenticator

    Authenticator.objects.get_or_create(
        user=utente, type=Authenticator.Type.TOTP, defaults={"data": {"secret": "A" * 16}}
    )


@pytest.fixture
def client_di(utenti) -> Callable[[str], Client]:
    def _client(ruolo: str) -> Client:
        c = Client()
        if ruolo != "anonimo":
            c.force_login(utenti[ruolo])
        return c

    return _client


@pytest.fixture
def edizione(db):
    from apps.editions.models import Edizione, StatoEdizione

    oggi = timezone.now().date()
    return Edizione.objects.create(
        anno=2098, stato=StatoEdizione.APERTA,
        scadenza_evento=oggi + timezone.timedelta(days=30),
        scadenza_assemblea=oggi + timezone.timedelta(days=60),
    )


@pytest.fixture
def diario(db, edizione, org, utenti) -> Diario:
    """Diario delle Tigri: Capo Squadriglia `utenti["csq"]`, Capo Reparto `utenti["crp"]`."""
    return Diario.objects.create(
        edizione=edizione, squadriglia=org["squadriglia"],
        csq=utenti["csq"].socio, crp=utenti["crp"].socio,
        tipo=TipoDiario.NUOVO, stato=StatoDiario.IN_COMPILAZIONE,
        scadenza_riferimento=ScadenzaRiferimento.PRIMA,
    )


def json_body(payload: dict) -> dict:
    """kwargs per Client.post/put/patch con corpo JSON: `c.post(url, **json_body({...}))`."""
    return {"data": json.dumps(payload), "content_type": "application/json"}
