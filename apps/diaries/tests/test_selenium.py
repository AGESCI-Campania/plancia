# apps/diaries/tests/test_selenium.py
"""Test Selenium (frontend) per le view cambio-referenti del Diario.

Usa Django LiveServer + Selenium WebDriver in modalità headless.
I test verificano:
- presenza dei pulsanti nella pagina di dettaglio
- compilazione del form via Tom Select (autocomplete AJAX)
- aggiornamento effettivo del database dopo la submit
"""
import pytest
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from apps.diaries.models import StatoDiario

# ---------------------------------------------------------------------------
# Fixture: Chrome headless driver (scope=session per riuso tra i test)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def chrome_options():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")
    return opts


@pytest.fixture(scope="session")
def driver(chrome_options):
    """Driver Chrome riutilizzato per tutta la sessione di test."""
    d = webdriver.Chrome(options=chrome_options)
    d.implicitly_wait(2)
    yield d
    d.quit()


# ---------------------------------------------------------------------------
# Helper: autenticazione via cookie di sessione
# ---------------------------------------------------------------------------

def _selenium_login(driver, live_server_url, user):
    """Inietta il cookie di sessione nel browser per autenticare l'utente.

    Usa ModelBackend come backend di sessione perché AxesStandaloneBackend
    (che è AUTHENTICATION_BACKENDS[0]) non implementa get_user.
    """
    driver.delete_all_cookies()
    session = SessionStore()
    session[SESSION_KEY] = str(user.pk)
    session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    session[HASH_SESSION_KEY] = user.get_session_auth_hash()
    session.save()

    # Visita il dominio prima di settare il cookie
    driver.get(live_server_url + "/accounts/login/")
    driver.add_cookie({
        "name": settings.SESSION_COOKIE_NAME,
        "value": session.session_key,
        "path": "/",
    })


def _wait(driver, seconds: int = 6) -> WebDriverWait:
    return WebDriverWait(driver, seconds)


# ---------------------------------------------------------------------------
# Test: visibilità pulsanti nel dettaglio diario
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestPulsantiDettaglio:
    """Il template detail.html mostra i pulsanti cambio-referenti ai ruoli corretti."""

    def test_crp_vede_pulsante_cambia_csq(self, driver, live_server, diario, user_crp):
        _selenium_login(driver, live_server.url, user_crp)
        driver.get(f"{live_server.url}/diari/{diario.pk}/")
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
        link = driver.find_element(By.LINK_TEXT, "Cambia Capo Squadriglia")
        assert link.is_displayed()

    def test_crp_non_vede_pulsante_cambia_crp(self, driver, live_server, diario, user_crp):
        _selenium_login(driver, live_server.url, user_crp)
        driver.get(f"{live_server.url}/diari/{diario.pk}/")
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
        links = driver.find_elements(By.LINK_TEXT, "Cambia Capo Reparto")
        assert len(links) == 0

    def test_admin_vede_entrambi_i_pulsanti(self, driver, live_server, diario, user_admin):
        _selenium_login(driver, live_server.url, user_admin)
        driver.get(f"{live_server.url}/diari/{diario.pk}/")
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
        assert driver.find_element(By.LINK_TEXT, "Cambia Capo Squadriglia").is_displayed()
        assert driver.find_element(By.LINK_TEXT, "Cambia Capo Reparto").is_displayed()

    def test_csq_non_vede_pulsanti_cambio(self, driver, live_server, diario, user_csq):
        _selenium_login(driver, live_server.url, user_csq)
        driver.get(f"{live_server.url}/diari/{diario.pk}/")
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
        assert len(driver.find_elements(By.LINK_TEXT, "Cambia Capo Squadriglia")) == 0
        assert len(driver.find_elements(By.LINK_TEXT, "Cambia Capo Reparto")) == 0

    def test_pulsanti_assenti_dopo_invio(self, driver, live_server, diario, user_admin):
        diario.stato = StatoDiario.INVIATO
        diario.save()
        _selenium_login(driver, live_server.url, user_admin)
        driver.get(f"{live_server.url}/diari/{diario.pk}/")
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
        assert len(driver.find_elements(By.LINK_TEXT, "Cambia Capo Squadriglia")) == 0
        assert len(driver.find_elements(By.LINK_TEXT, "Cambia Capo Reparto")) == 0
        # ripristina
        diario.stato = StatoDiario.IN_COMPILAZIONE
        diario.save()


# ---------------------------------------------------------------------------
# Helper: seleziona un socio via JavaScript API di Tom Select
# ---------------------------------------------------------------------------

def _tom_select_set(driver, select_id: str, pk: int, label: str, timeout: int = 8):
    """Imposta il valore del <select> sottostante Tom Select via DOM diretto.

    Aggira l'API di Tom Select (inaffidabile in headless Chrome) manipolando
    direttamente l'elemento <select>: rimuove `required`, aggiunge l'opzione
    con il pk corretto e la seleziona.  Il form submit seguente invierà il pk.
    """
    _wait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".ts-wrapper"))
    )
    driver.execute_script(
        """
        var select = document.getElementById(arguments[0]);
        select.removeAttribute('required');
        var option = document.createElement('option');
        option.value = String(arguments[1]);
        option.text = arguments[2];
        option.selected = true;
        select.appendChild(option);
        select.value = String(arguments[1]);
        """,
        select_id, pk, label,
    )


# ---------------------------------------------------------------------------
# Test: cambio CSQ via form Tom Select
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestCambiaCsqForm:
    """Il form cambia-csq funziona end-to-end nel browser."""

    def test_carica_pagina_cambia_csq(self, driver, live_server, diario, user_crp):
        _selenium_login(driver, live_server.url, user_crp)
        driver.get(f"{live_server.url}/diari/{diario.pk}/cambia-csq/")
        _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ts-wrapper")))
        assert "Cambia Capo Squadriglia" in driver.title

    def test_crp_sostituisce_csq_via_tom_select(
        self, driver, live_server, diario, user_crp, socio_csq_alt
    ):
        _selenium_login(driver, live_server.url, user_crp)
        driver.get(f"{live_server.url}/diari/{diario.pk}/cambia-csq/")
        _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ts-wrapper")))

        _tom_select_set(driver, "socio-ts", socio_csq_alt.pk, str(socio_csq_alt))
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        # Aspetta la navigazione verso il dettaglio diario
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))

        diario.refresh_from_db()
        assert diario.csq == socio_csq_alt

    def test_admin_sostituisce_csq_in_relazione_finale(
        self, driver, live_server, diario, user_admin, socio_csq_alt
    ):
        diario.stato = StatoDiario.RELAZIONE_FINALE
        diario.save()
        _selenium_login(driver, live_server.url, user_admin)
        driver.get(f"{live_server.url}/diari/{diario.pk}/cambia-csq/")
        _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ts-wrapper")))

        _tom_select_set(driver, "socio-ts", socio_csq_alt.pk, str(socio_csq_alt))
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))

        diario.refresh_from_db()
        assert diario.csq == socio_csq_alt
        # ripristina
        diario.stato = StatoDiario.IN_COMPILAZIONE
        diario.save()


# ---------------------------------------------------------------------------
# Test: cambio CRP via form Tom Select
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestCambiaCrpForm:
    """Il form cambia-crp funziona end-to-end nel browser."""

    def test_carica_pagina_cambia_crp(self, driver, live_server, diario, user_admin):
        _selenium_login(driver, live_server.url, user_admin)
        driver.get(f"{live_server.url}/diari/{diario.pk}/cambia-crp/")
        _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ts-wrapper")))
        assert "Cambia Capo Reparto" in driver.title

    def test_admin_sostituisce_crp_via_tom_select(
        self, driver, live_server, diario, user_admin, socio_crp_alt
    ):
        _selenium_login(driver, live_server.url, user_admin)
        driver.get(f"{live_server.url}/diari/{diario.pk}/cambia-crp/")
        _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ts-wrapper")))

        _tom_select_set(driver, "socio-ts", socio_crp_alt.pk, str(socio_crp_alt))
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))

        diario.refresh_from_db()
        assert diario.crp == socio_crp_alt


# ---------------------------------------------------------------------------
# Test: cambio CRP per reparto
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestCambiaCrpRepartoForm:
    """Il form cambia-crp-reparto mostra i diari coinvolti e aggiorna in bulk."""

    def test_carica_pagina_con_diari(self, driver, live_server, diario, user_admin):
        reparto_pk = diario.squadriglia.reparto_id
        _selenium_login(driver, live_server.url, user_admin)
        driver.get(f"{live_server.url}/diari/reparto/{reparto_pk}/cambia-crp/")
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "Cambia Capo Reparto" in driver.find_element(By.TAG_NAME, "h1").text
        # Il diario deve comparire nella lista
        page_src = driver.page_source
        assert diario.squadriglia.nome in page_src

    def test_admin_bulk_cambia_crp_reparto(
        self, driver, live_server, diario, user_admin, socio_crp_alt
    ):
        reparto_pk = diario.squadriglia.reparto_id
        _selenium_login(driver, live_server.url, user_admin)
        driver.get(f"{live_server.url}/diari/reparto/{reparto_pk}/cambia-crp/")
        _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ts-wrapper")))

        _tom_select_set(driver, "socio-ts", socio_crp_alt.pk, str(socio_crp_alt))
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        # Il bulk redirect va alla lista diari; aspetta il titolo della pagina
        _wait(driver).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))

        diario.refresh_from_db()
        assert diario.crp == socio_crp_alt
