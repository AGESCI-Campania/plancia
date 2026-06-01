# apps/accounts/tests/test_login_form.py
"""Test della risoluzione identificatore nel PlanciaLoginForm (codice socio, username, email)."""
import pytest

from apps.accounts.forms import PlanciaLoginForm
from apps.accounts.models import User
from apps.org.models import Categoria, Gruppo, Socio, Zona


@pytest.fixture
def zona(db):
    return Zona.objects.create(nome="Zona Test")


@pytest.fixture
def gruppo(zona):
    return Gruppo.objects.create(nome="Gruppo Test", zona=zona)


@pytest.fixture
def utente_con_socio(gruppo):
    socio = Socio.objects.create(
        codice_socio="12345",
        nome="Mario",
        cognome="Rossi",
        email="mario.rossi@esempio.it",
        categoria=Categoria.RAGAZZO,
        gruppo=gruppo,
        zona=gruppo.zona,
    )
    user = User.objects.create_user(
        username="m.rossi",
        email="mario.rossi@esempio.it",
        password="TestPass123!",
    )
    user.socio = socio
    user.save()
    return user


def _resolve(identifier: str) -> str:
    """Chiama clean_login in isolamento, senza passare per il clean() di allauth."""
    form = PlanciaLoginForm(data={"login": identifier, "password": "x"})
    form.cleaned_data = {"login": identifier}
    return form.clean_login()


@pytest.mark.django_db
class TestCleanLogin:
    def test_email_passthrough(self, utente_con_socio):
        """Un indirizzo email valido viene restituito invariato."""
        assert _resolve("mario.rossi@esempio.it") == "mario.rossi@esempio.it"

    def test_codice_socio_risolve_email(self, utente_con_socio):
        """Il codice socio numerico viene risolto nell'email dell'utente collegato."""
        assert _resolve("12345") == "mario.rossi@esempio.it"

    def test_username_risolve_email(self, utente_con_socio):
        """Lo username viene risolto nell'email dell'utente."""
        assert _resolve("m.rossi") == "mario.rossi@esempio.it"

    def test_username_case_insensitive(self, utente_con_socio):
        """La lookup per username è case-insensitive."""
        assert _resolve("M.ROSSI") == "mario.rossi@esempio.it"

    def test_codice_socio_inesistente_passthrough(self, db):
        """Un codice socio non nel DB viene restituito invariato (allauth gestirà l'errore)."""
        assert _resolve("99999") == "99999"

    def test_username_inesistente_passthrough(self, db):
        """Uno username non nel DB viene restituito invariato."""
        assert _resolve("utente.fantasma") == "utente.fantasma"

    def test_codice_troppo_corto_non_e_lookup(self, db):
        """Una stringa numerica sotto le 4 cifre non è trattata come codice socio."""
        assert _resolve("123") == "123"

    def test_codice_troppo_lungo_non_e_lookup(self, db):
        """Una stringa numerica sopra le 8 cifre non è trattata come codice socio."""
        assert _resolve("123456789") == "123456789"


@pytest.mark.django_db
class TestLoginIntegrazione:
    """Test end-to-end: POST alla view di login con codice socio o username."""

    def test_login_con_codice_socio(self, client, utente_con_socio):
        """L'utente riesce ad autenticarsi inserendo il codice socio al posto dell'email."""
        response = client.post(
            "/accounts/login/",
            {"login": "12345", "password": "TestPass123!"},
            follow=True,
        )
        assert response.context["user"].is_authenticated

    def test_login_con_username(self, client, utente_con_socio):
        """L'utente riesce ad autenticarsi inserendo lo username al posto dell'email."""
        response = client.post(
            "/accounts/login/",
            {"login": "m.rossi", "password": "TestPass123!"},
            follow=True,
        )
        assert response.context["user"].is_authenticated

    def test_login_con_email(self, client, utente_con_socio):
        """Il login tradizionale con email funziona ancora."""
        response = client.post(
            "/accounts/login/",
            {"login": "mario.rossi@esempio.it", "password": "TestPass123!"},
            follow=True,
        )
        assert response.context["user"].is_authenticated

    def test_login_password_errata_fallisce(self, client, utente_con_socio):
        """Con password errata il login non va a buon fine, anche se il codice socio è corretto."""
        response = client.post(
            "/accounts/login/",
            {"login": "12345", "password": "PasswordSbagliata!"},
        )
        assert not response.wsgi_request.user.is_authenticated
