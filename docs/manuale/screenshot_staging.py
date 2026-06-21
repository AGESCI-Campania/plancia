#!/usr/bin/env python
"""Screenshot per i manuali v2-offline — gira su staging (HTTPS, dati reali anonimizzati).

Uso:
    uv run python docs/manuale/screenshot_staging.py

Il script chiede il codice TOTP interattivamente se l'account richiede MFA.
Dopo ogni screenshot, offusca email e dati personali visibili con un rettangolo
grigio (Pillow). I PNG vengono salvati in docs/manuale/screenshots/.
"""

import os
import sys
import time

from PIL import Image, ImageDraw

# ── configurazione ────────────────────────────────────────────────────────────

BASE_URL    = "https://staging.plancia.agescicampania.org"
ADMIN_EMAIL = "andrea.bruno.phd@gmail.com"
ADMIN_PW    = "123PassSicura!"

# PK di un diario CSQ esistente su staging (impresa/1 confermata dal test)
DIARIO_PK   = 256

OUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")

# ── Selenium ──────────────────────────────────────────────────────────────────

def make_driver(mobile=False):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    if mobile:
        opts.add_argument("--window-size=390,844")   # iPhone 14
    else:
        opts.add_argument("--window-size=1280,900")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.implicitly_wait(6)
    return driver


def login(driver, email, password):
    driver.get(BASE_URL + "/accounts/login/")
    time.sleep(2)
    try:
        driver.find_element("id", "id_login").clear()
        driver.find_element("id", "id_login").send_keys(email)
        driver.find_element("id", "id_password").clear()
        driver.find_element("id", "id_password").send_keys(password)
        driver.find_element("css selector", "[type=submit]").click()
        time.sleep(2)
    except Exception as e:
        print(f"   ⚠ Errore login: {e}")

    # MFA step (se richiesto)
    if "/2fa/authenticate/" in driver.current_url or "/mfa/authenticate/" in driver.current_url:
        code = input("   🔐 Codice TOTP (6 cifre) per MFA: ").strip()
        try:
            field = driver.find_element("id", "id_code")
            field.clear()
            field.send_keys(code)
            driver.find_element("css selector", "[type=submit]").click()
            time.sleep(1.5)
        except Exception as e:
            print(f"   ⚠ Errore MFA: {e}")


def logout(driver):
    driver.get(BASE_URL + "/accounts/logout/")
    time.sleep(1)
    try:
        driver.find_element("css selector", "form [type=submit]").click()
        time.sleep(1)
    except Exception:
        pass


def shot(driver, name, url=None, wait=1.2, scroll_top=True):
    if url:
        driver.get(BASE_URL + url)
        time.sleep(wait)
    if scroll_top:
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(0.2)
    path = os.path.join(OUT_DIR, f"{name}.png")
    driver.save_screenshot(path)
    print(f"   📸 {name}.png")
    return path


def shot_bottom(driver, name, url=None, wait=1.2):
    """Screenshot del fondo della pagina (per footer/banner)."""
    if url:
        driver.get(BASE_URL + url)
        time.sleep(wait)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(0.3)
    path = os.path.join(OUT_DIR, f"{name}.png")
    driver.save_screenshot(path)
    print(f"   📸 {name}.png")
    return path


# ── offuscamento dati sensibili ───────────────────────────────────────────────

def blur_region(img_path, regions):
    """Copre le regioni (x, y, w, h) con un rettangolo grigio opaco."""
    img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    for (x, y, w, h) in regions:
        draw.rectangle([x, y, x + w, y + h], fill=(80, 80, 80, 255))
    img.convert("RGB").save(img_path)


def blur_header_email(img_path):
    """Offusca la zona header dove compare l'email admin (angolo in alto a destra)."""
    img = Image.open(img_path)
    w, _ = img.size
    # Copre ~200px da destra nel header (zona email/avatar), prima riga di navigazione
    blur_region(img_path, [(w - 250, 10, 240, 50)])


# ── CDP: simulazione offline ──────────────────────────────────────────────────

def set_offline(driver, offline: bool):
    """Attiva/disattiva modalità offline via Chrome DevTools Protocol."""
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.emulateNetworkConditions", {
        "offline": offline,
        "latency": 0,
        "downloadThroughput": -1,
        "uploadThroughput": -1,
    })
    time.sleep(0.5)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"\n── Screenshot staging: {BASE_URL}\n")

    driver = make_driver()
    driver_mobile = make_driver(mobile=True)

    try:
        # ── Login admin (desktop) ─────────────────────────────────
        print("→ Login admin (desktop)…")
        login(driver, ADMIN_EMAIL, ADMIN_PW)
        if "/accounts/" in driver.current_url or "login" in driver.current_url:
            print("   ⚠ Login fallito — verifica credenziali")
            return
        print(f"   ✓ Loggato come {ADMIN_EMAIL}")

        # ── Home admin (sidebar + badge) ──────────────────────────
        print("\n→ Schermate generali…")
        shot(driver, "19_home_admin", "/")
        blur_header_email(os.path.join(OUT_DIR, "19_home_admin.png"))

        # ── Lista diari (paginazione nuova) ───────────────────────
        shot(driver, "03_diari_lista", "/diari/", wait=1.5)

        # ── Dettaglio diario ──────────────────────────────────────
        shot(driver, "04_diario_dettaglio", f"/diari/{DIARIO_PK}/", wait=1.5)

        # ── Modulo impresa 1 con widget foto ─────────────────────
        print("\n→ Modulo impresa 1 con widget foto (online)…")
        shot(driver, "07_modulo_impresa1", f"/diari/{DIARIO_PK}/impresa/1/", wait=2)

        # ── Widget foto: scroll fino al widget ───────────────────
        driver.get(BASE_URL + f"/diari/{DIARIO_PK}/impresa/1/")
        time.sleep(2)
        driver.execute_script(
            "document.querySelector('[data-foto-base-url]')?.scrollIntoView({behavior:'instant',block:'center'})"
        )
        time.sleep(0.8)
        p = os.path.join(OUT_DIR, "41_foto_widget_online.png")
        driver.save_screenshot(p)
        print("   📸 41_foto_widget_online.png")

        # ── Badge offline nell'header (simula offline) ────────────
        print("\n→ Simulazione offline (CDP)…")
        driver.get(BASE_URL + f"/diari/{DIARIO_PK}/impresa/1/")
        time.sleep(2)
        set_offline(driver, True)
        time.sleep(1)
        shot(driver, "42_header_offline_badge", scroll_top=True)
        set_offline(driver, False)
        time.sleep(0.5)

        # ── Profilo / sidebar utente ──────────────────────────────
        print("\n→ Sidebar e profilo…")
        shot(driver, "20_utenti_admin", "/utenti/lista/", wait=1.2)
        shot(driver, "44_profilo", "/accounts/profile/", wait=1.2)
        blur_header_email(os.path.join(OUT_DIR, "44_profilo.png"))

        # ── Impostazioni ──────────────────────────────────────────
        shot(driver, "16_impostazioni", "/impostazioni/", wait=1.5)
        shot(driver, "36_cache_pdf", "/impostazioni/cache-pdf/", wait=1.5)
        shot(driver, "37_log_export", "/impostazioni/log-export/", wait=1.5)

        logout(driver)

        # ── Login mobile (impersonazione CSQ) ─────────────────────
        print("\n→ Login admin mobile per screenshot CSQ…")
        login(driver_mobile, ADMIN_EMAIL, ADMIN_PW)
        if "/accounts/" not in driver_mobile.current_url and "login" not in driver_mobile.current_url:
            # Naviga al diario come admin (vede tutto)
            shot(driver_mobile, "02_home_csq_mobile", "/", wait=1.5)
            shot(driver_mobile, "43_impresa_mobile",
                 f"/diari/{DIARIO_PK}/impresa/1/", wait=2)

            # ── offline mobile: badge in sospeso ─────────────────
            driver_mobile.get(BASE_URL + f"/diari/{DIARIO_PK}/impresa/1/")
            time.sleep(2)
            set_offline(driver_mobile, True)
            time.sleep(1)
            p = os.path.join(OUT_DIR, "45_offline_mobile.png")
            driver_mobile.save_screenshot(p)
            print("   📸 45_offline_mobile.png")
            set_offline(driver_mobile, False)

            logout(driver_mobile)

    finally:
        driver.quit()
        driver_mobile.quit()

    print(f"\n✓ Screenshot salvati in {OUT_DIR}")


if __name__ == "__main__":
    main()
