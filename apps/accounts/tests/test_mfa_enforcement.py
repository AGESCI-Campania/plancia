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

def _attiva_totp(user) -> None:
    import json

    from allauth.mfa.models import Authenticator

    Authenticator.objects.create(
        user=user, type=Authenticator.Type.TOTP, data=json.dumps({"secret": "A" * 32})
    )


@pytest.mark.django_db
class TestMFAEnforcementMiddleware:
    """Percorsi Django rimasti (admin, proxy): 403 a chi deve configurare la MFA.

    La configurazione si fa dalla SPA via allauth headless; l'API ha la sua regola
    (apps/api/auth.py) e qui non viene toccata.
    """

    PERCORSI_DJANGO = ("/admin/", "/mailadmin/", "/celery/")

    @pytest.mark.parametrize("percorso", PERCORSI_DJANGO)
    def test_admin_senza_mfa_riceve_403(self, client, utente_admin, percorso):
        client.force_login(utente_admin)
        response = client.get(percorso)
        assert response.status_code == 403
        assert b"verifica in due passaggi" in response.content.lower()
        assert "/profilo/sicurezza" in response.content.decode()

    @pytest.mark.parametrize("utente", ["utente_segreteria", "utente_iabr"])
    def test_ruoli_estesi_senza_mfa_ricevono_403(self, client, utente, request):
        client.force_login(request.getfixturevalue(utente))
        assert client.get("/admin/").status_code == 403

    def test_csq_senza_mfa_non_bloccato(self, client, utente_csq):
        client.force_login(utente_csq)
        # Non è staff: l'admin lo rimanda all'accesso, ma il middleware non risponde 403.
        assert client.get("/admin/").status_code == 302

    def test_admin_con_mfa_accede_all_admin(self, client, utente_admin):
        utente_admin.is_staff = utente_admin.is_superuser = True
        utente_admin.save()
        _attiva_totp(utente_admin)
        client.force_login(utente_admin)
        assert client.get("/admin/").status_code == 200

    def test_admin_senza_mfa_usa_allauth_headless_e_api_me(self, client, utente_admin):
        """/_allauth/ serve proprio a configurare la MFA: non va bloccato."""
        client.force_login(utente_admin)
        assert client.get("/_allauth/browser/v1/auth/session").status_code != 403
        assert client.get("/api/v1/me").status_code == 200

    def test_admin_senza_mfa_non_bloccato_su_healthz(self, client, utente_admin):
        client.force_login(utente_admin)
        assert client.get("/healthz/").status_code == 200

    def test_utente_non_autenticato_non_bloccato(self, client):
        response = client.get("/admin/")
        assert response.status_code == 302


@pytest.mark.django_db
class TestAccessoAdminDjango:
    """L'admin non usa il proprio form password: rimanda all'accesso della SPA."""

    def test_anonimo_su_admin_va_alla_spa(self, client):
        response = client.get("/admin/", follow=True)
        assert response.redirect_chain[-1][0] == "/accesso?next=%2Fadmin%2F"

    def test_login_admin_rimanda_alla_spa_con_next(self, client):
        response = client.get("/admin/login/?next=/admin/siteconfig/")
        assert response.status_code == 302
        assert response["Location"] == "/accesso?next=%2Fadmin%2Fsiteconfig%2F"

    def test_post_password_sul_login_admin_non_autentica(self, client, utente_admin):
        response = client.post(
            "/admin/login/", {"username": utente_admin.email, "password": "Pass123!"}
        )
        assert response.status_code == 302
        assert response["Location"].startswith("/accesso")
        assert "_auth_user_id" not in client.session

    def test_next_esterno_ignorato(self, client):
        response = client.get("/admin/login/?next=https://esempio.it/")
        assert response["Location"] == "/accesso?next=%2Fadmin%2F"


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
