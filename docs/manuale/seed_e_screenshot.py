#!/usr/bin/env python
"""Script: seed dati dimostrativi + screenshot con Selenium (headless Chrome).

Uso:
    uv run python docs/manuale/seed_e_screenshot.py

Richiede: server Django già avviato su http://127.0.0.1:8000
          (uv run python manage.py runserver 0.0.0.0:8000)
"""

import os
import sys
import time
import django

# ── setup Django ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()


# ── seed dati ─────────────────────────────────────────────────────────────────
def seed():
    from django.utils import timezone
    from apps.accounts.models import User, Ruolo
    from apps.org.models import Zona, Gruppo, Reparto, Squadriglia, Socio, Categoria
    from apps.editions.models import Edizione, StatoEdizione
    from apps.diaries.models import (
        Diario, TipoDiario, StatoDiario, Anagrafica, Presentazione,
        Impresa, Missione, EsitoSpecialita, TipoEsito, MembroSq, PostoAzione,
        PostoAzioneMissione,
    )

    print("→ Seed zona/gruppo/reparto/squadriglie…")
    zona, _ = Zona.objects.get_or_create(nome="ZONA HIRPINIA")
    gruppo, _ = Gruppo.objects.get_or_create(nome="AVELLINO 1", zona=zona)
    reparto, _ = Reparto.objects.get_or_create(nome="Reparto Aquile", gruppo=gruppo)
    squadriglia, _ = Squadriglia.objects.get_or_create(nome="Aquila", reparto=reparto)
    squadriglia2, _ = Squadriglia.objects.get_or_create(nome="Lepre", reparto=reparto)
    squadriglia3, _ = Squadriglia.objects.get_or_create(nome="Pantera", reparto=reparto)

    print("→ Seed soci…")
    crp_socio, _ = Socio.objects.get_or_create(
        codice_socio="100001",
        defaults=dict(nome="Mario", cognome="Rossi", categoria=Categoria.CAPO,
                      email="crp@plancia.it", gruppo=gruppo, zona=zona),
    )
    pgv_socio, _ = Socio.objects.get_or_create(
        codice_socio="100002",
        defaults=dict(nome="Giulia", cognome="Verdi", categoria=Categoria.CAPO,
                      email="pgv@plancia.it", gruppo=gruppo, zona=zona),
    )
    incaricato_socio, _ = Socio.objects.get_or_create(
        codice_socio="100003",
        defaults=dict(nome="Anna", cognome="Neri", categoria=Categoria.CAPO,
                      email="incaricato@plancia.it", gruppo=gruppo, zona=zona),
    )
    csq_socio, _ = Socio.objects.get_or_create(
        codice_socio="200001",
        defaults=dict(nome="Luca", cognome="Bianchi", categoria=Categoria.RAGAZZO,
                      email="csq@plancia.it", gruppo=gruppo, zona=zona),
    )

    print("→ Link utenti ↔ soci e password…")
    admin = User.objects.filter(email="admin@plancia.it").first()
    if admin:
        admin.set_password("admin123")
        admin.save(update_fields=["password"])

    seg = User.objects.filter(email="segreteria@plancia.it").first()
    if seg:
        seg.set_password("test123")
        seg.save(update_fields=["password"])

    pgv_user = User.objects.filter(email="pgv@plancia.it").first()
    if pgv_user:
        pgv_user.set_password("test123")
        pgv_user.ruolo = Ruolo.PGV
        pgv_user.socio = pgv_socio
        pgv_user.save(update_fields=["password", "ruolo", "socio"])

    incaricato_user, created = User.objects.get_or_create(
        email="incaricato@plancia.it",
        defaults=dict(username="incaricato_eg", ruolo=Ruolo.INCARICATO_EG, socio=incaricato_socio),
    )
    if created or not incaricato_user.has_usable_password():
        incaricato_user.set_password("test123")
        incaricato_user.save(update_fields=["password"])
    incaricato_user.ruolo = Ruolo.INCARICATO_EG
    incaricato_user.socio = incaricato_socio
    incaricato_user.save(update_fields=["ruolo", "socio"])

    crp_user, created = User.objects.get_or_create(
        email="crp@plancia.it",
        defaults=dict(username="crp", ruolo=Ruolo.CRP, socio=crp_socio),
    )
    if created or not crp_user.has_usable_password():
        crp_user.set_password("test123")
        crp_user.save(update_fields=["password"])
    crp_user.socio = crp_socio
    crp_user.save(update_fields=["socio"])

    csq_user = User.objects.filter(email="csq@plancia.it").first()
    if csq_user:
        csq_user.set_password("test123")
        csq_user.ruolo = Ruolo.CSQ
        csq_user.socio = csq_socio
        csq_user.save(update_fields=["password", "ruolo", "socio"])

    print("→ MFA (TOTP) per utenti privilegiati…")
    totp_secrets = {
        "admin@plancia.it": _crea_totp_se_mancante(admin),
        "segreteria@plancia.it": _crea_totp_se_mancante(seg),
        "incaricato@plancia.it": _crea_totp_se_mancante(incaricato_user),
    }

    print("→ Edizione…")
    ed = Edizione.objects.first()
    if ed and ed.stato not in (StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE):
        ed.stato = StatoEdizione.APERTA
        ed.save(update_fields=["stato"])

    print("→ Diario principale (CSQ/CRP) + tutti i moduli…")
    diario = None
    if ed:
        diario, diario_creato = Diario.objects.get_or_create(
            squadriglia=squadriglia,
            edizione=ed,
            defaults=dict(
                csq=csq_socio, crp=crp_socio,
                tipo=TipoDiario.NUOVO,
                stato=StatoDiario.IN_COMPILAZIONE,
            ),
        )

        if diario.stato != StatoDiario.IN_COMPILAZIONE:
            diario.stato = StatoDiario.IN_COMPILAZIONE
            diario.save(update_fields=["stato"])

        # Modulo 1 — Anagrafica
        ana, _ = Anagrafica.objects.get_or_create(
            diario=diario,
            defaults=dict(
                crp_nome="Mario", crp_cognome="Rossi",
                crp_email="crp@plancia.it", crp_cell="3330000001",
                specialita="Esplorazione",
                partecipa_evento=True,
            ),
        )
        from apps.diaries.models import SPECIALITA_SQUADRIGLIA
        if ana.specialita not in SPECIALITA_SQUADRIGLIA:
            ana.specialita = "Esplorazione"
            ana.save(update_fields=["specialita"])

        # Modulo 2 — Presentazione + Membri
        pres, _ = Presentazione.objects.get_or_create(
            diario=diario,
            defaults=dict(cosa_sappiamo_fare="Siamo una squadriglia affiatata con competenze in orientamento, campismo e tecniche di segnalazione."),
        )
        if not pres.membri.exists():
            MembroSq.objects.create(presentazione=pres, nome="Luca", cognome="Bianchi", ruolo="csq", sentiero="responsabilita")
            MembroSq.objects.create(presentazione=pres, nome="Sofia", cognome="Ferrari", ruolo="vcsq", sentiero="competenza")
            MembroSq.objects.create(presentazione=pres, nome="Marco", cognome="Conti", ruolo="squadrigliere", sentiero="competenza")
            MembroSq.objects.create(presentazione=pres, nome="Elena", cognome="Russo", ruolo="squadrigliere", sentiero="scoperta")
            MembroSq.objects.create(presentazione=pres, nome="Davide", cognome="Marino", ruolo="squadrigliere", sentiero="scoperta")

        # Modulo 3 — 1ª Impresa
        imp1, _ = Impresa.objects.get_or_create(
            diario=diario, numero=1,
            defaults=dict(
                titolo="Sentiero del Parco Regionale del Matese",
                data_inizio="2025-09-20", data_fine="2025-09-21",
                perche="Conoscere il territorio e sviluppare le tecniche di orientamento e campismo.",
                come="Escursione di 2 giorni con pernottamento in tenda nel Parco del Matese.",
                cosa="Relazione scritta con mappa dell'itinerario, foto e racconto dell'esperienza.",
            ),
        )
        if not imp1.posti_azione.exists():
            PostoAzione.objects.create(impresa=imp1, descrizione="Allestimento del campo base e preparazione dei pasti")
            PostoAzione.objects.create(impresa=imp1, descrizione="Navigazione con bussola e mappa topografica")
        imp1.esiti_specialita.all().delete()
        EsitoSpecialita.objects.create(impresa=imp1, tipo=TipoEsito.SPECIALITA, nome="Campeggiatore", stato="in_cammino")
        EsitoSpecialita.objects.create(impresa=imp1, tipo=TipoEsito.SPECIALITA, nome="Topografo", stato="in_cammino")
        EsitoSpecialita.objects.create(impresa=imp1, tipo=TipoEsito.BREVETTO, nome="Pioniere", stato="in_cammino")

        # Modulo 4 — 2ª Impresa
        imp2, _ = Impresa.objects.get_or_create(
            diario=diario, numero=2,
            defaults=dict(
                titolo="Laboratorio di Giornalismo Locale",
                data_inizio="2025-11-08", data_fine="2025-11-08",
                perche="Sviluppare le capacità di comunicazione e documentare la vita del reparto.",
                come="Realizzazione di un giornalino di squadriglia con articoli, interviste e foto.",
                cosa="Giornalino stampato e distribuito al reparto e alle famiglie.",
            ),
        )
        if not imp2.posti_azione.exists():
            PostoAzione.objects.create(impresa=imp2, descrizione="Redazione degli articoli e impaginazione")
            PostoAzione.objects.create(impresa=imp2, descrizione="Intervista a un ex-scout del gruppo")
        imp2.esiti_specialita.all().delete()
        EsitoSpecialita.objects.create(impresa=imp2, tipo=TipoEsito.SPECIALITA, nome="Redattore", stato="in_cammino")
        EsitoSpecialita.objects.create(impresa=imp2, tipo=TipoEsito.SPECIALITA, nome="Fotografo", stato="conquistata")
        EsitoSpecialita.objects.create(impresa=imp2, tipo=TipoEsito.BREVETTO, nome="Giornalista", stato="in_cammino")

        # Modulo 5 — Missione
        miss, _ = Missione.objects.get_or_create(
            diario=diario,
            defaults=dict(
                titolo="Servizio alla Sagra della Castagna",
                data="2025-10-19",
                descrizione_svolgimento="La squadriglia ha prestato servizio durante la Sagra della Castagna di Montemarano, gestendo l'accoglienza visitatori, il servizio ai tavoli e la raccolta fondi per il centro di recupero animali locali.",
            ),
        )
        if not miss.posti_azione.exists():
            PostoAzioneMissione.objects.create(missione=miss, descrizione="Accoglienza e informazioni ai visitatori")
            PostoAzioneMissione.objects.create(missione=miss, descrizione="Raccolta fondi per il canile municipale")

        print(f"   Diario {diario.pk} (Aquila, IN_COMPILAZIONE) — moduli CSQ presenti.")

    print("→ Diario Lepre (INVIATO) per screenshot Incaricato…")
    diario_inviato = None
    if ed:
        diario_inviato, _ = Diario.objects.get_or_create(
            squadriglia=squadriglia2,
            edizione=ed,
            defaults=dict(
                csq=csq_socio, crp=crp_socio,
                tipo=TipoDiario.NUOVO,
                stato=StatoDiario.INVIATO,
            ),
        )
        if diario_inviato.stato != StatoDiario.INVIATO:
            diario_inviato.stato = StatoDiario.INVIATO
            diario_inviato.save(update_fields=["stato"])
        print(f"   Diario {diario_inviato.pk} (Lepre, INVIATO).")

    print("→ Diario Pantera (IN_VALUTAZIONE) per screenshot Pattuglia GV…")
    diario_valutazione = None
    if ed and pgv_user:
        diario_valutazione, _ = Diario.objects.get_or_create(
            squadriglia=squadriglia3,
            edizione=ed,
            defaults=dict(
                csq=csq_socio, crp=crp_socio,
                tipo=TipoDiario.NUOVO,
                stato=StatoDiario.IN_VALUTAZIONE,
            ),
        )
        if diario_valutazione.stato != StatoDiario.IN_VALUTAZIONE:
            diario_valutazione.stato = StatoDiario.IN_VALUTAZIONE
            diario_valutazione.save(update_fields=["stato"])

        from apps.evaluations.models import Valutazione, AssegnazionePGV
        val, _ = Valutazione.objects.get_or_create(diario=diario_valutazione)
        AssegnazionePGV.objects.get_or_create(
            valutazione=val,
            pgv=pgv_user,
            defaults={"assegnato_da": incaricato_user},
        )
        print(f"   Diario {diario_valutazione.pk} (Pantera, IN_VALUTAZIONE) — PGV assegnata.")

    return {
        "admin": ("admin@plancia.it", "admin123"),
        "segreteria": ("segreteria@plancia.it", "test123"),
        "pgv": ("pgv@plancia.it", "test123"),
        "incaricato": ("incaricato@plancia.it", "test123"),
        "crp": ("crp@plancia.it", "test123"),
        "csq": ("csq@plancia.it", "test123"),
        "diario_pk": diario.pk if diario else None,
        "diario_inviato_pk": diario_inviato.pk if diario_inviato else None,
        "diario_valutazione_pk": diario_valutazione.pk if diario_valutazione else None,
        "edizione_pk": ed.pk if ed else None,
        "reparto_pk": reparto.pk,
        "totp_secrets": totp_secrets,
    }


def _crea_totp_se_mancante(user):
    """Crea un TOTP per bypassare MFAEnforcementMiddleware. Restituisce il segreto (B32)."""
    if user is None:
        return None
    from allauth.mfa.models import Authenticator
    from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
    from allauth.mfa.utils import decrypt
    auth = Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).first()
    if auth:
        return decrypt(auth.data["secret"])
    secret = generate_totp_secret()
    TOTP.activate(user, secret)
    print(f"   TOTP creato per {user.email}")
    return secret


def _totp_code_now(secret_b32: str) -> str:
    """Calcola il codice TOTP corrente dal segreto B32 (non richiede riavvio server)."""
    import base64, hashlib, hmac as _hmac, struct, time
    counter = int(time.time()) // 30
    key = base64.b32decode(secret_b32.encode("ascii"), casefold=True)
    for delta in (0, -1, 1):
        c = counter + delta
        msg = struct.pack(">Q", c)
        h = _hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        code = (struct.unpack(">I", bytes([h[offset] & 0x7F]) + h[offset+1:offset+4])[0]) % 1_000_000
        if code != 0:
            return f"{code:06d}"
    return f"{(struct.unpack('>I', bytes([h[offset] & 0x7F]) + h[offset+1:offset+4])[0]) % 1_000_000:06d}"


# ── screenshot helper ─────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
OUT_DIR  = os.path.join(os.path.dirname(__file__), "screenshots")


def make_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--disable-gpu")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.implicitly_wait(6)
    return driver


def login(driver, email, password, totp_secret=None):
    driver.get(BASE_URL + "/accounts/login/")
    time.sleep(1.2)
    try:
        field = driver.find_element("id", "id_login")
    except Exception:
        try:
            driver.find_element("css selector", "[type=submit]").click()
            time.sleep(0.8)
        except Exception:
            pass
        driver.get(BASE_URL + "/accounts/login/")
        time.sleep(1.2)
        field = driver.find_element("id", "id_login")
    field.clear()
    field.send_keys(email)
    driver.find_element("id", "id_password").clear()
    driver.find_element("id", "id_password").send_keys(password)
    driver.find_element("css selector", "[type=submit]").click()
    time.sleep(1.5)
    if "/accounts/2fa/authenticate/" in driver.current_url:
        try:
            code = _totp_code_now(totp_secret) if totp_secret else "000000"
            code_field = driver.find_element("id", "id_code")
            code_field.clear()
            code_field.send_keys(code)
            driver.find_element("css selector", "[type=submit]").click()
            time.sleep(1.2)
            print(f"   MFA verificato per {email} (codice: {code})")
        except Exception as exc:
            print(f"   ⚠ Pagina MFA non gestita su {driver.current_url}: {exc}")


def _hide_djdt(driver):
    driver.execute_script("""
        var dj = document.getElementById('djdt');
        if (dj) dj.style.display = 'none';
        var djb = document.getElementById('djHideToolBarButton');
        if (djb) djb.click();
    """)


def shot(driver, name, url=None, wait=1.0):
    if url:
        driver.get(BASE_URL + url)
        time.sleep(wait)
    _hide_djdt(driver)
    time.sleep(0.2)
    path = os.path.join(OUT_DIR, f"{name}.png")
    driver.save_screenshot(path)
    print(f"   📸 {name}.png  [{driver.title[:60]}]")
    return path


def logout(driver):
    driver.get(BASE_URL + "/accounts/logout/")
    time.sleep(0.8)
    try:
        btn = driver.find_element("css selector", "form [type=submit]")
        btn.click()
        time.sleep(0.8)
    except Exception:
        pass


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("── Seed dati ───────────────────────────────────────────────")
    ctx = seed()
    diario_pk            = ctx["diario_pk"]
    diario_inviato_pk    = ctx["diario_inviato_pk"]
    diario_valutazione_pk = ctx["diario_valutazione_pk"]
    edizione_pk          = ctx["edizione_pk"]
    reparto_pk           = ctx["reparto_pk"]
    totp                 = ctx.get("totp_secrets", {})

    print("\n── Screenshot ──────────────────────────────────────────────")
    driver = make_driver()
    try:
        # ── 01. Login page ────────────────────────────────────────
        driver.get(BASE_URL + "/accounts/login/")
        time.sleep(1)
        shot(driver, "01_login")

        # ── 02–09. Capo Squadriglia ───────────────────────────────
        login(driver, *ctx["csq"])
        shot(driver, "02_home_csq", "/")
        shot(driver, "03_diari_lista", "/diari/")
        if diario_pk:
            shot(driver, "04_diario_dettaglio",     f"/diari/{diario_pk}/")
            shot(driver, "05_modulo_anagrafica",    f"/diari/{diario_pk}/anagrafica/",     wait=1.5)
            shot(driver, "06_modulo_presentazione", f"/diari/{diario_pk}/presentazione/",  wait=1.5)
            shot(driver, "07_modulo_impresa1",      f"/diari/{diario_pk}/impresa/1/",      wait=1.5)
            shot(driver, "08_modulo_impresa2",      f"/diari/{diario_pk}/impresa/2/",      wait=1.5)
            shot(driver, "09_modulo_missione",      f"/diari/{diario_pk}/missione/",       wait=1.5)
        logout(driver)

        # ── 10–11, 21–23. Capo Reparto ───────────────────────────
        login(driver, *ctx["crp"])
        shot(driver, "10_home_crp", "/")
        if diario_pk:
            shot(driver, "21_lista_diari_crp",      "/diari/")
            shot(driver, "22_dettaglio_diario_crp", f"/diari/{diario_pk}/")
            shot(driver, "23_cambia_csq",           f"/diari/{diario_pk}/cambia-csq/",    wait=1.5)
            shot(driver, "11_relazione_finale",     f"/diari/{diario_pk}/relazione/",     wait=1.5)
        logout(driver)

        # ── 12–13, 24. Pattuglia GV ──────────────────────────────
        login(driver, *ctx["pgv"])
        shot(driver, "12_home_pgv", "/")
        shot(driver, "13_diari_pgv", "/diari/")
        if diario_valutazione_pk:
            shot(driver, "24_valutazione_pgv",
                 f"/valutazioni/diari/{diario_valutazione_pk}/", wait=1.2)
        logout(driver)

        # ── 25–27. Incaricato EG ─────────────────────────────────
        inc_email, inc_pw = ctx["incaricato"]
        login(driver, inc_email, inc_pw, totp_secret=totp.get(inc_email))
        shot(driver, "25_home_incaricato", "/")
        shot(driver, "26_diari_incaricato", "/diari/")
        if diario_inviato_pk:
            shot(driver, "27_assegna_pgv",
                 f"/valutazioni/diari/{diario_inviato_pk}/", wait=1.2)
        logout(driver)

        # ── 14–18, 28–29. Segreteria ─────────────────────────────
        seg_email, seg_pw = ctx["segreteria"]
        login(driver, seg_email, seg_pw, totp_secret=totp.get(seg_email))
        shot(driver, "14_home_segreteria", "/")
        shot(driver, "15_utenti_lista",    "/utenti/utenti/")
        shot(driver, "16_impostazioni",    "/impostazioni/",       wait=1.5)
        shot(driver, "17_import_storico",  "/import/")
        if edizione_pk:
            shot(driver, "18_edizione_detail", f"/edizioni/{edizione_pk}/", wait=1.2)
        shot(driver, "28_gestione_inviti", "/notifiche/inviti/",   wait=1.2)
        shot(driver, "29_cambia_crp_reparto",
             f"/diari/reparto/{reparto_pk}/cambia-crp/",            wait=1.2)
        logout(driver)

        # ── 19–20, 30. Admin ─────────────────────────────────────
        adm_email, adm_pw = ctx["admin"]
        login(driver, adm_email, adm_pw, totp_secret=totp.get(adm_email))
        shot(driver, "19_home_admin", "/")
        shot(driver, "20_utenti_admin", "/utenti/utenti/",         wait=1)
        shot(driver, "30_mfa_impostazione", "/accounts/2fa/",      wait=1)
        logout(driver)

    finally:
        driver.quit()

    print(f"\n✓ Screenshot salvati in: {OUT_DIR}")
    print("  Ora esegui: uv run python docs/manuale/genera_manuale.py")


if __name__ == "__main__":
    main()
