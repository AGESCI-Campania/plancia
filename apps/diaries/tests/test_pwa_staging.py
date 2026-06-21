# apps/diaries/tests/test_pwa_staging.py
"""Test E2E PWA v2-offline — eseguiti contro staging (HTTPS con Service Worker attivo).

Questi test richiedono staging raggiungibile e NON usano il LiveServer Django
perché il Service Worker richiede HTTPS. Eseguire con:

    pytest apps/diaries/tests/test_pwa_staging.py -v \
        --staging-url=https://staging.plancia.agescicampania.org \
        --staging-email=andrea.bruno.phd@gmail.com \
        --staging-password=<password>

Oppure con variabili d'ambiente:
    STAGING_URL=... STAGING_EMAIL=... STAGING_PASSWORD=... pytest ...

I test coprono:
    - Service worker: cache navigazione HTML
    - Offline navigation: pagine servite dalla cache SW
    - Optimistic locking: version conflict 409
    - Sync post-login: coda IndexedDB svuotata dopo 401
"""
import os
import time

import pytest
import requests

pytestmark = pytest.mark.skipif(
    not os.environ.get("STAGING_PASSWORD"),
    reason="Test E2E staging: impostare STAGING_PASSWORD per eseguirli",
)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# ── Configurazione ──────────────────────────────────────────────────────────

STAGING_URL   = os.environ.get("STAGING_URL",   "https://staging.plancia.agescicampania.org")
STAGING_EMAIL = os.environ.get("STAGING_EMAIL", "andrea.bruno.phd@gmail.com")
STAGING_PWD   = os.environ.get("STAGING_PASSWORD", "")

DIARIO_PK = 301  # diario usato nei test — deve esistere su staging


def pytest_addoption(parser):
    parser.addoption("--staging-url",      default=STAGING_URL)
    parser.addoption("--staging-email",    default=STAGING_EMAIL)
    parser.addoption("--staging-password", default=STAGING_PWD)


@pytest.fixture(scope="module")
def staging(request):
    return {
        "url":      request.config.getoption("--staging-url",      default=STAGING_URL),
        "email":    request.config.getoption("--staging-email",     default=STAGING_EMAIL),
        "password": request.config.getoption("--staging-password",  default=STAGING_PWD),
    }


@pytest.fixture(scope="module")
def browser():
    """Chrome headless con viewport mobile."""
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=390,844")
    driver = webdriver.Chrome(options=opts)
    yield driver
    driver.quit()


@pytest.fixture(scope="module")
def logged_in_browser(browser, staging):
    """Browser già autenticato su staging."""
    wait = WebDriverWait(browser, 15)
    browser.get(f"{staging['url']}/accounts/login/")
    wait.until(EC.presence_of_element_located((By.NAME, "login")))
    browser.find_element(By.NAME, "login").send_keys(staging["email"])
    browser.find_element(By.NAME, "password").send_keys(staging["password"])
    browser.find_element(By.CSS_SELECTOR, "[type=submit]").click()
    wait.until(EC.url_contains("/edizioni/"))
    time.sleep(2)  # attendi attivazione SW
    return browser


@pytest.fixture(scope="module")
def api_session(staging):
    """Sessione requests autenticata su staging."""
    s = requests.Session()
    s.get(f"{staging['url']}/accounts/login/")
    csrf = s.cookies["csrftoken"]
    s.post(
        f"{staging['url']}/accounts/login/",
        data={
            "login": staging["email"],
            "password": staging["password"],
            "csrfmiddlewaretoken": csrf,
        },
        headers={"Referer": f"{staging['url']}/accounts/login/"},
        allow_redirects=True,
    )
    return s


# ── Helper ──────────────────────────────────────────────────────────────────

def get_sw_cache(driver, cache_name="plancia-dynamic-v4"):
    return driver.execute_script(f"""
        return new Promise(resolve => {{
            caches.open('{cache_name}').then(cache =>
                cache.keys().then(keys => resolve(keys.map(r => r.url)))
            ).catch(() => resolve([]));
        }});
    """)


def set_offline(driver, offline=True):
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.emulateNetworkConditions", {{
        "offline": offline,
        "latency": 0,
        "downloadThroughput": -1 if not offline else 0,
        "uploadThroughput":  -1 if not offline else 0,
    }})


# ── Test: Service Worker cache ───────────────────────────────────────────────

class TestServiceWorkerCache:

    PAGES = [
        f"/diari/{DIARIO_PK}/",
        f"/diari/{DIARIO_PK}/anagrafica/",
        f"/diari/{DIARIO_PK}/impresa/1/",
    ]

    def test_pages_cached_after_visit(self, logged_in_browser, staging):
        """Le pagine del diario finiscono in plancia-dynamic-v4 dopo la visita."""
        driver = logged_in_browser
        wait = WebDriverWait(driver, 10)

        for p in self.PAGES:
            driver.get(f"{staging['url']}{p}")
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
            time.sleep(0.5)
        time.sleep(1)

        cached = get_sw_cache(driver)
        for p in self.PAGES:
            assert any(p in url for url in cached), \
                f"Pagina non in cache SW: {p}\nCache: {cached}"

    def test_offline_navigation_serves_cached_pages(self, logged_in_browser, staging):
        """Offline: le pagine già visitate vengono servite dalla cache SW."""
        driver = logged_in_browser

        # Visita prima online
        wait = WebDriverWait(driver, 10)
        for p in self.PAGES:
            driver.get(f"{staging['url']}{p}")
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
            time.sleep(0.4)
        time.sleep(1)

        # Passa offline
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.emulateNetworkConditions", {
            "offline": True, "latency": 0,
            "downloadThroughput": 0, "uploadThroughput": 0,
        })

        try:
            for p in self.PAGES:
                driver.get(f"{staging['url']}{p}")
                time.sleep(0.8)
                is_offline_page = (
                    "offline" in driver.current_url.lower()
                    or "sei offline" in driver.page_source.lower()
                )
                has_main = bool(driver.find_elements(By.TAG_NAME, "main"))
                assert has_main and not is_offline_page, \
                    f"Pagina non servita dalla cache offline: {p}"
        finally:
            driver.execute_cdp_cmd("Network.emulateNetworkConditions", {
                "offline": False, "latency": 0,
                "downloadThroughput": -1, "uploadThroughput": -1,
            })

    def test_auth_pages_never_cached(self, logged_in_browser, staging):
        """/accounts/ non finisce mai nella cache SW (CSRF token fresco obbligatorio)."""
        driver = logged_in_browser
        cached = get_sw_cache(driver)
        auth_cached = [url for url in cached if "/accounts/" in url]
        assert not auth_cached, \
            f"Pagine /accounts/ trovate in cache (CSRF risk): {auth_cached}"


# ── Test: Optimistic locking ─────────────────────────────────────────────────

class TestOptimisticLocking:

    def _api_url(self, staging):
        return f"{staging['url']}/api/diari/{DIARIO_PK}/modulo/anagrafica/"

    def _put(self, session, url, payload):
        csrf = session.cookies.get("csrftoken", "")
        return session.put(url, json=payload, headers={
            "X-CSRFToken": csrf,
            "Content-Type": "application/json",
            "Referer": url.replace("/api/diari/", "/diari/").replace("/modulo/anagrafica/", "/anagrafica/"),
            "X-Requested-With": "XMLHttpRequest",
        })

    def test_stale_version_returns_409(self, api_session, staging):
        """Una PUT con version stale viene rifiutata con 409 Conflict."""
        url = self._api_url(staging)
        data = api_session.get(url).json()
        version = data["version"]

        r1 = self._put(api_session, url, data)
        assert r1.status_code == 200, f"Prima PUT fallita: {r1.status_code}"

        # Ripete con la stessa version (ora stale)
        r2 = self._put(api_session, url, data)
        assert r2.status_code == 409, \
            f"Atteso 409 per version stale, got {r2.status_code}: {r2.text[:100]}"
        body = r2.json()
        assert body.get("error") == "conflict"
        assert "server_version" in body

    def test_current_version_accepted(self, api_session, staging):
        """Una PUT con version aggiornata viene accettata."""
        url = self._api_url(staging)
        data = api_session.get(url).json()

        r = self._put(api_session, url, data)
        assert r.status_code == 200
        new_version = r.json()["version"]
        assert new_version == data["version"] + 1

    def test_conflict_response_includes_server_version(self, api_session, staging):
        """Il corpo del 409 include server_version per permettere il merge."""
        url = self._api_url(staging)
        data = api_session.get(url).json()
        self._put(api_session, url, data)  # avanza la version

        r = self._put(api_session, url, data)  # version stale
        assert r.status_code == 409
        body = r.json()
        assert isinstance(body.get("server_version"), int)


# ── Test: Termina sessioni ───────────────────────────────────────────────────

class TestTerminaSessioni:

    def test_termina_sessioni_richiede_post(self, api_session, staging):
        """GET su /utenti/termina-sessioni/ deve restituire 405."""
        r = api_session.get(f"{staging['url']}/utenti/termina-sessioni/")
        assert r.status_code == 405

    def test_termina_sessioni_redirect_a_profilo(self, api_session, staging):
        """POST su termina-sessioni redirige al profilo."""
        csrf = api_session.cookies.get("csrftoken", "")
        r = api_session.post(
            f"{staging['url']}/utenti/termina-sessioni/",
            data={"csrfmiddlewaretoken": csrf},
            headers={"Referer": f"{staging['url']}/utenti/profilo/"},
            allow_redirects=False,
        )
        assert r.status_code in (302, 303)
        assert "profilo" in r.headers.get("Location", "")
