"""Test dell'integrazione SSO con Sestante (docs/guide/sso_sestante.md)."""
import pytest
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from apps.accounts.adapters import (
    PlanciaSocialAccountAdapter,
    _sync_ruoli_globali,
    sessione_da_sestante,
)
from apps.accounts.models import Nomina, Ruolo, User

METODO_SESTANTE = {"method": "socialaccount", "provider": "sestante", "uid": "abc"}
METODO_PASSWORD = {"method": "password", "email": "x@test.it"}


def _crea_utente(email: str, ruolo: str = Ruolo.CSQ) -> User:
    u = User.objects.create_user(username=email, email=email, password="Pass123!")
    u.ruolo = ruolo
    u.save()
    return u


def _richiesta():
    request = RequestFactory().get("/accounts/oidc/sestante/login/callback/")
    request.session = SessionStore()
    request.user = type("Anon", (), {"is_authenticated": False})()
    return request


def _sociallogin(email: str | None, groups: list[str], uid: str = "sub-1") -> SocialLogin:
    account = SocialAccount(
        provider="sestante",
        uid=uid,
        extra_data={"userinfo": {"email": email, "groups": groups}, "id_token": {}},
    )
    indirizzi = [EmailAddress(email=email, verified=False, primary=True)] if email else []
    return SocialLogin(
        user=User(email=email or "", username=email or uid),
        account=account,
        email_addresses=indirizzi,
    )


def _ruoli_sso_attivi(user) -> set[str]:
    return set(
        Nomina.objects.filter(utente=user, da_sso=True, attiva=True).values_list("ruolo", flat=True)
    )


# ---------------------------------------------------------------------------
# Metodo di autenticazione della sessione
# ---------------------------------------------------------------------------

class TestSessioneDaSestante:
    def test_sessione_sso(self):
        request = _richiesta()
        request.session["account_authentication_methods"] = [METODO_SESTANTE]
        assert sessione_da_sestante(request) is True

    def test_sessione_password(self):
        request = _richiesta()
        request.session["account_authentication_methods"] = [METODO_PASSWORD]
        assert sessione_da_sestante(request) is False

    def test_altro_provider_social(self):
        request = _richiesta()
        request.session["account_authentication_methods"] = [
            {"method": "socialaccount", "provider": "google"}
        ]
        assert sessione_da_sestante(request) is False

    def test_richiesta_senza_sessione(self):
        assert sessione_da_sestante(object()) is False


@pytest.mark.django_db
class TestMiddlewareMFAConSSO:
    """Bypass della MFA solo per le sessioni aperte via Sestante (percorsi Django e API)."""

    PAGINA_PROTETTA = "/admin/"

    def _imposta_metodi(self, client, metodi):
        session = client.session
        session["account_authentication_methods"] = metodi
        session.save()

    def test_admin_entrato_via_sso_non_deve_configurare_mfa(self, client):
        admin = _crea_utente("admin@test.it", Ruolo.ADMIN)
        admin.is_staff = True
        admin.save()
        client.force_login(admin)
        self._imposta_metodi(client, [METODO_SESTANTE])
        assert client.get(self.PAGINA_PROTETTA).status_code == 200
        assert client.get("/api/v1/edizioni").status_code == 200

    def test_admin_collegato_a_sestante_ma_entrato_con_password(self, client):
        """L'account collegato non basta: conta il metodo di login della sessione."""
        admin = _crea_utente("admin@test.it", Ruolo.ADMIN)
        SocialAccount.objects.create(user=admin, provider="sestante", uid="sub-admin")
        client.force_login(admin)
        self._imposta_metodi(client, [METODO_PASSWORD])
        assert client.get(self.PAGINA_PROTETTA).status_code == 403
        r = client.get("/api/v1/edizioni")
        assert r.status_code == 403
        assert r.json()["mfa_da_configurare"] is True


class TestCallbackSestante:
    """La callback è registrata nel blueprint di Sestante: non deve cambiare (HEADLESS_ONLY)."""

    CALLBACK = "/accounts/oidc/sestante/login/callback/"

    def test_reverse(self):
        from django.urls import reverse

        url = reverse("openid_connect_callback", kwargs={"provider_id": "sestante"})
        assert url == self.CALLBACK

    def test_resolve(self):
        from django.urls import resolve

        match = resolve(self.CALLBACK)
        assert match.url_name == "openid_connect_callback"
        assert match.kwargs == {"provider_id": "sestante"}

    def test_pagine_allauth_django_assenti(self):
        """Con HEADLESS_ONLY non esistono più le pagine di login/MFA di Django."""
        from django.urls import NoReverseMatch, reverse

        for nome in ("account_login", "mfa_activate_totp", "account_change_password"):
            with pytest.raises(NoReverseMatch):
                reverse(nome)


# ---------------------------------------------------------------------------
# Sincronizzazione dei ruoli globali
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSyncRuoliGlobali:
    def test_assegna_ruolo_globale(self):
        u = _crea_utente("a@test.it")
        _sync_ruoli_globali(u, ["admin-multipiattaforma", "gruppo-interno-authentik"])
        u.refresh_from_db()
        assert u.ruolo == Ruolo.ADMIN
        assert _ruoli_sso_attivi(u) == {Ruolo.ADMIN}

    def test_idempotente(self):
        u = _crea_utente("a@test.it")
        _sync_ruoli_globali(u, ["segreteria"])
        _sync_ruoli_globali(u, ["segreteria"])
        assert Nomina.objects.filter(utente=u, da_sso=True).count() == 1

    def test_revoca_riporta_al_default(self):
        u = _crea_utente("a@test.it")
        _sync_ruoli_globali(u, ["segreteria"])
        _sync_ruoli_globali(u, [])
        u.refresh_from_db()
        assert u.ruolo == Ruolo.CSQ
        assert _ruoli_sso_attivi(u) == set()
        # La nomina revocata resta per l'audit trail
        assert Nomina.objects.filter(utente=u, da_sso=True, attiva=False).count() == 1

    def test_revoca_torna_al_ruolo_locale(self):
        u = _crea_utente("a@test.it", Ruolo.INCARICATO_EG)
        Nomina.objects.create(utente=u, ruolo=Ruolo.INCARICATO_EG)
        _sync_ruoli_globali(u, ["segreteria"])
        u.refresh_from_db()
        assert u.ruolo == Ruolo.SEGRETERIA
        _sync_ruoli_globali(u, [])
        u.refresh_from_db()
        assert u.ruolo == Ruolo.INCARICATO_EG
        assert Nomina.objects.filter(utente=u, ruolo=Ruolo.INCARICATO_EG, attiva=True).exists()

    def test_nomina_locale_di_admin_non_toccata(self):
        u = _crea_utente("a@test.it", Ruolo.ADMIN)
        Nomina.objects.create(utente=u, ruolo=Ruolo.ADMIN)
        _sync_ruoli_globali(u, [])
        u.refresh_from_db()
        assert u.ruolo == Ruolo.ADMIN
        assert Nomina.objects.filter(utente=u, ruolo=Ruolo.ADMIN, da_sso=False, attiva=True).exists()

    def test_superutente_senza_gruppi_resta_admin(self):
        u = User.objects.create_superuser(username="su@test.it", email="su@test.it", password="x")
        u.refresh_from_db()
        _sync_ruoli_globali(u, [])
        u.refresh_from_db()
        assert u.ruolo == Ruolo.ADMIN

    def test_ruolo_globale_minore_non_cambia_ruolo_attivo(self):
        u = _crea_utente("a@test.it", Ruolo.ADMIN)
        Nomina.objects.create(utente=u, ruolo=Ruolo.ADMIN)
        _sync_ruoli_globali(u, ["segreteria"])
        u.refresh_from_db()
        assert u.ruolo == Ruolo.ADMIN
        assert set(u.ruoli_attivi) == {Ruolo.ADMIN, Ruolo.SEGRETERIA}


# ---------------------------------------------------------------------------
# Adapter: collegamento per email, rifiuti, provisioning
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdapterSestante:
    adapter = PlanciaSocialAccountAdapter()

    @pytest.fixture(autouse=True)
    def _provider_sestante(self, settings):
        settings.SOCIALACCOUNT_PROVIDERS = {
            "openid_connect": {
                "SERVERS": [
                    {
                        "id": "sestante",
                        "name": "SSO AGESCI Campania",
                        "server_url": "https://auth.example.test/application/o/plancia/",
                        "APP": {"client_id": "id-test", "secret": "secret-test"},
                    }
                ]
            }
        }

    def test_collega_utente_esistente_per_email(self):
        u = _crea_utente("Mario.Rossi@test.it", Ruolo.CRP)
        sl = _sociallogin("mario.rossi@test.it", ["segreteria"])
        self.adapter.pre_social_login(_richiesta(), sl)
        assert SocialAccount.objects.filter(user=u, provider="sestante").exists()
        assert User.objects.filter(email__iexact="mario.rossi@test.it").count() == 1
        u.refresh_from_db()
        assert u.ruolo == Ruolo.SEGRETERIA

    def test_email_marcate_verificate(self):
        sl = _sociallogin("nuovo@test.it", [])
        self.adapter.pre_social_login(_richiesta(), sl)
        assert all(e.verified for e in sl.email_addresses)

    def test_senza_email_rifiutato(self):
        utenti_prima = User.objects.count()
        sl = _sociallogin(None, [])
        with pytest.raises(ImmediateHttpResponse) as exc:
            self.adapter.pre_social_login(_richiesta(), sl)
        assert User.objects.count() == utenti_prima
        # Torna alla pagina di accesso della SPA con il messaggio
        assert exc.value.response["Location"].startswith("/accesso?errore=")

    def test_email_duplicata_rifiutata(self):
        _crea_utente("doppio@test.it")
        _crea_utente("DOPPIO@test.it")
        sl = _sociallogin("doppio@test.it", [])
        with pytest.raises(ImmediateHttpResponse):
            self.adapter.pre_social_login(_richiesta(), sl)
        assert not SocialAccount.objects.exists()

    def test_auto_signup_solo_per_sestante(self):
        sl = _sociallogin("nuovo@test.it", [])
        assert self.adapter.is_auto_signup_allowed(_richiesta(), sl) is True
        sl.account.provider = "google"
        assert self.adapter.is_auto_signup_allowed(_richiesta(), sl) is False

    def test_nuovo_utente_riceve_ruolo_globale(self):
        sl = _sociallogin("nuovo@test.it", ["admin-multipiattaforma"])
        user = self.adapter.save_user(_richiesta(), sl)
        user.refresh_from_db()
        assert user.ruolo == Ruolo.ADMIN
        assert _ruoli_sso_attivi(user) == {Ruolo.ADMIN}

    def test_nuovo_utente_senza_gruppi(self):
        sl = _sociallogin("nuovo@test.it", ["gruppo-interno-authentik"])
        user = self.adapter.save_user(_richiesta(), sl)
        user.refresh_from_db()
        assert user.ruolo == Ruolo.CSQ
        assert user.ruoli_attivi == []


# ---------------------------------------------------------------------------
# Nome dai claim di Sestante
# ---------------------------------------------------------------------------

class TestNomeDaSestante:
    def test_nome_intero_senza_cognome_inventato(self):
        """authentik: given_name = nome intero, niente family_name."""
        sl = _sociallogin("andrea@test.it", [])
        dati = {"email": "andrea@test.it", "name": "Andrea Bruno", "first_name": "Andrea Bruno", "last_name": None}
        user = PlanciaSocialAccountAdapter().populate_user(_richiesta(), sl, dati)
        assert (user.first_name, user.last_name) == ("Andrea Bruno", "")
        assert user.nome_completo == "Andrea Bruno"

    def test_altri_provider_invariati(self):
        sl = _sociallogin("mario@test.it", [])
        sl.account.provider = "google"
        dati = {"email": "mario@test.it", "first_name": "Mario", "last_name": "Rossi"}
        user = PlanciaSocialAccountAdapter().populate_user(_richiesta(), sl, dati)
        assert (user.first_name, user.last_name) == ("Mario", "Rossi")


# ---------------------------------------------------------------------------
# Configurazione effettiva del provider (config/settings/base.py)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_provider_sestante_chiede_lo_scope_avatar(settings):
    """Gli scope che allauth chiede davvero: con il vecchio formato SERVERS `SCOPE` si perdeva."""
    from allauth.socialaccount.adapter import get_adapter

    from config.settings.base import SESTANTE_APP

    settings.SOCIALACCOUNT_PROVIDERS = {"openid_connect": {"APPS": [{**SESTANTE_APP, "client_id": "id-test"}]}}
    provider = get_adapter().get_provider(_richiesta(), "sestante")
    assert provider.get_scope() == ["openid", "profile", "email", "avatar"]
    assert provider.server_url == (
        "https://auth.agescicampania.net/application/o/plancia/.well-known/openid-configuration"
    )
