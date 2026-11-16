"""Impianto comune dell'API: gestori di errore e fixture per ruolo."""
import pytest

from apps.api.tests.conftest import RUOLI_TEST

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("ruolo", RUOLI_TEST)
def test_me_per_ogni_ruolo(client_di, utenti, ruolo):
    r = client_di(ruolo).get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["ruolo"]["chiave"] == utenti[ruolo].ruolo


def test_anonimo_non_autenticato(client_di):
    assert client_di("anonimo").get("/api/v1/me").status_code == 401


def test_pgv_vede_solo_i_diari_assegnati(client_di, diario):
    assert client_di("pgv").get(f"/api/v1/diari/{diario.pk}").status_code in (403, 404)
    assert client_di("crp").get(f"/api/v1/diari/{diario.pk}").status_code == 200


def test_mfa_obbligatoria_anche_sulle_api(client_di, utenti, settings):
    """Admin senza MFA: solo il proprio profilo finché non la configura."""
    from allauth.mfa.models import Authenticator

    settings.SKIP_MFA_ENFORCEMENT = False
    settings.DEBUG = False
    Authenticator.objects.filter(user=utenti["admin"]).delete()
    c = client_di("admin")
    me = c.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["mfa_da_configurare"] is True
    r = c.get("/api/v1/utenti")
    assert r.status_code == 403
    assert r.json()["mfa_da_configurare"] is True


def test_mfa_configurata_api_libere(client_di, settings):
    settings.SKIP_MFA_ENFORCEMENT = False
    settings.DEBUG = False
    assert client_di("admin").get("/api/v1/utenti").status_code == 200


def test_nomi_degli_schemi_unici():
    """ninja nomina gli schemi OpenAPI con il nome della classe: due classi omonime in moduli
    diversi si sovrascrivono in silenzio (e i tipi generati per la SPA sono sbagliati)."""
    import importlib
    import inspect
    import pkgutil
    from collections import defaultdict

    from ninja import Schema

    import apps.api.routers
    import apps.api.schemas

    definiti: dict[str, set[str]] = defaultdict(set)
    for pacchetto in (apps.api.schemas, apps.api.routers):
        for info in pkgutil.iter_modules(pacchetto.__path__):
            modulo = importlib.import_module(f"{pacchetto.__name__}.{info.name}")
            for nome, classe in inspect.getmembers(modulo, inspect.isclass):
                if issubclass(classe, Schema) and classe.__module__ == modulo.__name__:
                    definiti[nome].add(modulo.__name__)
    assert {n: m for n, m in definiti.items() if len(m) > 1} == {}
