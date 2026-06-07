# apps/accounts/tests/test_mfa_enforcement.py
"""Test dell'enforcement MFA per ruoli privilegiati (docs sez. 2 e 12)."""
import pytest

from apps.accounts.adapters import PlanciaMFAAdapter, ruolo_richiede_mfa
from apps.accounts.models import Ruolo, User

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

def _crea_utente(ruolo: str, **kwargs) -> User:
    email = kwargs.pop("email", f"{ruolo}@test.it")
    u = User.objects.create_user(username=email, email=email, password="Pass123!")
    u.ruolo = ruolo
    u.save()
    return u


@pytest.fixture
def utente_admin(db):
    return _crea_utente(Ruolo.ADMIN)


@pytest.fixture
def utente_segreteria(db):
    return _crea_utente(Ruolo.SEGRETERIA)


@pytest.fixture
def utente_iabr(db):
    return _crea_utente(Ruolo.INCARICATO_EG)


@pytest.fixture
def utente_csq(db):
    return _crea_utente(Ruolo.CSQ)


@pytest.fixture
def utente_crp(db):
    return _crea_utente(Ruolo.CRP)


# ---------------------------------------------------------------------------
# Test ruolo_richiede_mfa
# ---------------------------------------------------------------------------

class TestRuoloRichiedeMfa:
    def test_admin_richiede_mfa(self):
        class FakeUser:
            ruolo = Ruolo.ADMIN
            mfa_obbligatoria = False
            is_superuser = False
        assert ruolo_richiede_mfa(FakeUser()) is True

    def test_segreteria_richiede_mfa(self):
        class FakeUser:
            ruolo = Ruolo.SEGRETERIA
            mfa_obbligatoria = False
            is_superuser = False
        assert ruolo_richiede_mfa(FakeUser()) is True

    def test_incaricato_eg_richiede_mfa(self):
        class FakeUser:
            ruolo = Ruolo.INCARICATO_EG
            mfa_obbligatoria = False
            is_superuser = False
        assert ruolo_richiede_mfa(FakeUser()) is True

    def test_csq_non_richiede_mfa(self):
        class FakeUser:
            ruolo = Ruolo.CSQ
            mfa_obbligatoria = False
            is_superuser = False
        assert ruolo_richiede_mfa(FakeUser()) is False

    def test_crp_non_richiede_mfa(self):
        class FakeUser:
            ruolo = Ruolo.CRP
            mfa_obbligatoria = False
            is_superuser = False
        assert ruolo_richiede_mfa(FakeUser()) is False

    def test_flag_mfa_obbligatoria_forza_indipendentemente_dal_ruolo(self):
        class FakeUser:
            ruolo = Ruolo.CSQ
            mfa_obbligatoria = True
            is_superuser = False
        assert ruolo_richiede_mfa(FakeUser()) is True

    def test_superuser_richiede_mfa(self):
        class FakeUser:
            ruolo = Ruolo.CSQ
            mfa_obbligatoria = False
            is_superuser = True
        assert ruolo_richiede_mfa(FakeUser()) is True


# ---------------------------------------------------------------------------
# Test middleware (via client HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMFAEnforcementMiddleware:
    """Testa il comportamento del middleware su richieste HTTP reali."""

    PAGINA_PROTETTA = "/edizioni/"
    PAGINA_MFA_SETUP = "/accounts/2fa/totp/activate/"

    def test_csq_senza_mfa_accede_liberamente(self, client, utente_csq):
        client.force_login(utente_csq)
        response = client.get(self.PAGINA_PROTETTA)
        # Non deve essere reindirizzato alla pagina MFA
        assert response.status_code != 302 or self.PAGINA_MFA_SETUP not in response.get("Location", "")

    def test_admin_senza_mfa_viene_reindirizzato(self, client, utente_admin):
        client.force_login(utente_admin)
        response = client.get(self.PAGINA_PROTETTA)
        assert response.status_code == 302
        assert self.PAGINA_MFA_SETUP in response["Location"]

    def test_segreteria_senza_mfa_viene_reindirizzata(self, client, utente_segreteria):
        client.force_login(utente_segreteria)
        response = client.get(self.PAGINA_PROTETTA)
        assert response.status_code == 302
        assert self.PAGINA_MFA_SETUP in response["Location"]

    def test_iabr_senza_mfa_viene_reindirizzato(self, client, utente_iabr):
        client.force_login(utente_iabr)
        response = client.get(self.PAGINA_PROTETTA)
        assert response.status_code == 302
        assert self.PAGINA_MFA_SETUP in response["Location"]

    def test_admin_con_mfa_accede_liberamente(self, client, utente_admin):
        """Un Admin con TOTP attivo non viene bloccato."""
        import json

        from allauth.mfa.models import Authenticator
        Authenticator.objects.create(
            user=utente_admin,
            type=Authenticator.Type.TOTP,
            data=json.dumps({"secret": "A" * 32}),
        )
        client.force_login(utente_admin)
        response = client.get(self.PAGINA_PROTETTA)
        assert self.PAGINA_MFA_SETUP not in response.get("Location", "")

    def test_admin_senza_mfa_puo_accedere_a_percorsi_accounts(self, client, utente_admin):
        """Il middleware non blocca i percorsi /accounts/ per evitare loop infiniti.

        Allauth può fare i propri redirect all'interno di /accounts/ (es. reauthenticate
        prima di modificare impostazioni di sicurezza): l'importante è che il nostro
        middleware non reindirizzi verso mfa_activate_totp da qui.
        """
        client.force_login(utente_admin)
        response = client.get("/accounts/2fa/totp/activate/")
        assert self.PAGINA_MFA_SETUP not in response.get("Location", "")

    def test_admin_senza_mfa_non_bloccato_su_logout(self, client, utente_admin):
        client.force_login(utente_admin)
        response = client.get("/accounts/logout/")
        assert self.PAGINA_MFA_SETUP not in response.get("Location", "")

    def test_utente_non_autenticato_non_bloccato(self, client):
        response = client.get(self.PAGINA_PROTETTA)
        assert self.PAGINA_MFA_SETUP not in response.get("Location", "")


# ---------------------------------------------------------------------------
# Test PlanciaMFAAdapter.can_delete_authenticator
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCanDeleteAuthenticator:
    def _crea_authenticator(self, user, tipo):
        import json

        from allauth.mfa.models import Authenticator
        return Authenticator(
            user=user,
            type=tipo,
            data=json.dumps({"secret": "A" * 32}),
        )

    def test_admin_non_puo_rimuovere_totp(self, utente_admin):
        from allauth.mfa.models import Authenticator
        auth = self._crea_authenticator(utente_admin, Authenticator.Type.TOTP)
        assert PlanciaMFAAdapter().can_delete_authenticator(auth) is False

    def test_admin_puo_rigenerare_recovery_codes(self, utente_admin):
        from allauth.mfa.models import Authenticator
        auth = self._crea_authenticator(utente_admin, Authenticator.Type.RECOVERY_CODES)
        assert PlanciaMFAAdapter().can_delete_authenticator(auth) is True

    def test_csq_puo_rimuovere_totp(self, utente_csq):
        from allauth.mfa.models import Authenticator
        auth = self._crea_authenticator(utente_csq, Authenticator.Type.TOTP)
        assert PlanciaMFAAdapter().can_delete_authenticator(auth) is True
