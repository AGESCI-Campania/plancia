"""API impostazioni: sezioni, footer, pagine statiche, template email, test email, Gmail OAuth,
log export, cache PDF, progresso task, axes, manutenzione."""
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.api.tests.conftest import json_body
from apps.notifications.models import MailTemplate
from apps.siteconfig.models import FooterLink, Impostazioni, PaginaStatica

pytestmark = pytest.mark.django_db

BASE = "/api/v1/impostazioni"
STAFF = ["admin", "segreteria", "incaricato_eg"]
NON_STAFF = ["pgv", "crp", "csq"]


@pytest.fixture(autouse=True)
def senza_rate_limit(monkeypatch):
    """Il contatore del rate limit (cache del processo) non deve accumularsi tra i test."""
    monkeypatch.setattr("apps.siteconfig.middleware._rate_limit_check", lambda *a, **k: (True, 0))


@pytest.fixture(autouse=True)
def cache_pulita():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def imp(db):
    imp = Impostazioni.objects.get_or_create(pk=1)[0]
    imp.smtp_password = "segreto-smtp"
    imp.email_provider_api_key = "chiave-api"
    imp.save()
    return imp


# --- Lettura e sezioni ---------------------------------------------------------

@pytest.mark.parametrize("ruolo", STAFF)
def test_leggi_impostazioni_staff(client_di, imp, ruolo):
    r = client_di(ruolo).get(BASE)
    assert r.status_code == 200
    body = r.json()
    assert body["identita"]["titolo"] == imp.titolo
    assert body["email"]["smtp_password_impostato"] is True
    assert body["email"]["email_provider_api_key_impostato"] is True
    assert body["email"]["email_provider_webhook_secret_impostato"] is False
    assert "segreto-smtp" not in r.content.decode()
    assert "chiave-api" not in r.content.decode()
    assert body["email"]["webhook_url"].endswith("/anymail/webhook/")


@pytest.mark.parametrize("ruolo", NON_STAFF)
def test_leggi_impostazioni_vietata(client_di, ruolo):
    assert client_di(ruolo).get(BASE).status_code == 403


def test_leggi_impostazioni_anonimo(client_di):
    assert client_di("anonimo").get(BASE).status_code == 401


def test_patch_identita(client_di, imp):
    r = client_di("segreteria").patch(f"{BASE}/identita", **json_body({"titolo": "Nuovo titolo"}))
    assert r.status_code == 200
    assert r.json()["identita"]["titolo"] == "Nuovo titolo"
    imp.refresh_from_db()
    assert imp.titolo == "Nuovo titolo"
    assert imp.sottotitolo  # invariato
    assert Impostazioni.get().titolo == "Nuovo titolo"  # cache aggiornata


def test_patch_sezione_vietata(client_di, imp):
    assert client_di("crp").patch(f"{BASE}/identita", **json_body({"titolo": "X"})).status_code == 403


def test_patch_email_segreti_invariati(client_di, imp):
    r = client_di("admin").patch(f"{BASE}/email", **json_body({
        "from_email": "noreply@example.it", "smtp_password": "", "email_provider_api_key": None,
    }))
    assert r.status_code == 200
    imp.refresh_from_db()
    assert imp.from_email == "noreply@example.it"
    assert imp.smtp_password == "segreto-smtp"
    assert imp.email_provider_api_key == "chiave-api"
    client_di("admin").patch(f"{BASE}/email", **json_body({"smtp_password": "nuova"}))
    imp.refresh_from_db()
    assert imp.smtp_password == "nuova"


def test_patch_email_validazione_form(client_di, imp):
    """Stessi controlli del form web: invio reale via SMTP senza host → errore sul campo."""
    r = client_di("admin").patch(f"{BASE}/email", **json_body({
        "email_mode": "reale", "email_provider": "smtp", "smtp_host": "",
    }))
    assert r.status_code == 422
    assert "smtp_host" in r.json()["errori"]


def test_patch_email_gmail_oauth_non_tocca_smtp(client_di, imp):
    imp.smtp_use_gmail_oauth = True
    imp.smtp_host = "smtp.esempio.it"
    imp.save()
    client_di("admin").patch(f"{BASE}/email", **json_body({"smtp_host": "altro.it"}))
    imp.refresh_from_db()
    assert imp.smtp_host == "smtp.esempio.it"


def test_patch_sicurezza_e_allegati(client_di, imp):
    c = client_di("incaricato_eg")
    r = c.patch(f"{BASE}/sicurezza", **json_body({"mfa_obbligatoria_ruoli_estesi": False}))
    assert r.status_code == 200
    assert r.json()["sicurezza"]["mfa_obbligatoria_ruoli_estesi"] is False
    assert r.json()["sicurezza"]["axes_failure_limit"] == 5
    assert c.patch(f"{BASE}/allegati", **json_body({"allegati_max_px": 800})).status_code == 200
    imp.refresh_from_db()
    assert imp.allegati_max_px == 800
    assert imp.mfa_obbligatoria_ruoli_estesi is False


def test_manutenzione(client_di, imp):
    c = client_di("admin")
    assert c.get(f"{BASE}/manutenzione").json() == {"manutenzione": False, "messaggio": ""}
    assert c.put(f"{BASE}/manutenzione", **json_body({"attiva": True})).json()["manutenzione"]
    imp.refresh_from_db()
    assert imp.manutenzione is True
    # l'API resta raggiungibile in manutenzione (il middleware bypassa /api/v1/)
    assert c.put(f"{BASE}/manutenzione", **json_body({"attiva": False})).status_code == 200
    assert client_di("pgv").get(f"{BASE}/manutenzione").status_code == 403


def test_patch_diagnostica(client_di, imp):
    r = client_di("admin").patch(f"{BASE}/diagnostica", **json_body({"debug_diagnostico": True}))
    assert r.json()["diagnostica"] == {
        "manutenzione": False, "manutenzione_messaggio": "", "debug_toolbar": False,
        "debug_diagnostico": True,
    }


def test_messaggio_manutenzione(client_di, imp):
    c = client_di("admin")
    r = c.patch(f"{BASE}/diagnostica",
                **json_body({"manutenzione": True, "manutenzione_messaggio": "  Torniamo alle 18  "}))
    assert r.status_code == 200
    assert r.json()["diagnostica"]["manutenzione_messaggio"] == "Torniamo alle 18"
    imp.refresh_from_db()
    assert imp.manutenzione is True and imp.manutenzione_messaggio == "Torniamo alle 18"
    # un PATCH senza messaggio non lo tocca
    c.patch(f"{BASE}/diagnostica", **json_body({"debug_toolbar": True}))
    imp.refresh_from_db()
    assert imp.manutenzione_messaggio == "Torniamo alle 18"
    # PUT /manutenzione: messaggio facoltativo
    r = c.put(f"{BASE}/manutenzione", **json_body({"attiva": False}))
    assert r.json() == {"manutenzione": False, "messaggio": "Torniamo alle 18"}
    r = c.put(f"{BASE}/manutenzione", **json_body({"attiva": True, "messaggio": ""}))
    assert r.json() == {"manutenzione": True, "messaggio": ""}


def test_patch_footer_testo(client_di, imp):
    r = client_di("admin").patch(f"{BASE}/footer", **json_body({"footer_testo": "<b>Ciao</b>"}))
    assert r.json()["footer"]["footer_testo"] == "<b>Ciao</b>"


# --- Footer link ---------------------------------------------------------------

def test_footer_link_crud_e_ordine(client_di, imp):
    c = client_di("segreteria")
    r1 = c.post(f"{BASE}/footer/link", **json_body({"url": "https://a.it", "etichetta": "A"}))
    assert r1.status_code == 201
    assert r1.json()["tipo"] == "sito_web"  # dedotto come nel form web
    r2 = c.post(f"{BASE}/footer/link",
                **json_body({"tipo": "email", "url": "mailto:x@y.it"}))
    a, b = r1.json()["id"], r2.json()["id"]
    assert [x["id"] for x in c.get(f"{BASE}/footer/link").json()] == [a, b]

    assert c.post(f"{BASE}/footer/link/ordina", **json_body({"ids": [b, a]})).status_code == 200
    assert [x["id"] for x in c.get(f"{BASE}/footer/link").json()] == [b, a]
    assert c.post(f"{BASE}/footer/link/ordina", **json_body({"ids": [a]})).status_code == 422

    r = c.patch(f"{BASE}/footer/link/{a}", **json_body({"etichetta": "Sito"}))
    assert r.status_code == 200 and r.json()["etichetta"] == "Sito"
    assert r.json()["url"] == "https://a.it"

    assert c.delete(f"{BASE}/footer/link/{a}").status_code == 204
    assert not FooterLink.objects.filter(pk=a).exists()
    assert c.delete(f"{BASE}/footer/link/{a}").status_code == 404


def test_footer_link_validazione_e_massimo(client_di, imp):
    c = client_di("admin")
    r = c.post(f"{BASE}/footer/link", **json_body({"tipo": "facebook", "url": ""}))
    assert r.status_code == 422 and "url" in r.json()["errori"]
    for i in range(4):
        assert c.post(f"{BASE}/footer/link",
                      **json_body({"url": f"https://{i}.it"})).status_code == 201
    assert c.post(f"{BASE}/footer/link", **json_body({"url": "https://5.it"})).status_code == 422


def test_footer_link_vietato(client_di, imp):
    assert client_di("csq").post(f"{BASE}/footer/link",
                                 **json_body({"url": "https://a.it"})).status_code == 403


# --- Pagine statiche -------------------------------------------------------------

def test_pagina_pubblica_anonimo(client_di):
    r = client_di("anonimo").get(f"{BASE}/pagine/privacy")
    assert r.status_code == 200
    assert r.json()["titolo"] == "Privacy Policy"
    assert client_di("anonimo").get(f"{BASE}/pagine/inesistente").status_code == 404


def test_pagina_modifica_e_importa(client_di):
    c = client_di("incaricato_eg")
    r = c.put(f"{BASE}/pagine/termini", **json_body({"titolo": "Termini", "contenuto": "<p>T</p>"}))
    assert r.status_code == 200
    assert client_di("anonimo").get(f"{BASE}/pagine/termini").json()["contenuto"] == "<p>T</p>"
    assert c.put(f"{BASE}/pagine/termini", **json_body({"titolo": ""})).status_code == 422
    r = c.post(f"{BASE}/pagine/privacy/importa")
    assert r.status_code in (200, 422)  # 422 se manca il file predefinito
    if r.status_code == 200:
        assert PaginaStatica.objects.get(slug="privacy").contenuto
    assert len(c.get(f"{BASE}/pagine").json()) == 2


def test_pagina_modifica_vietata(client_di):
    assert client_di("crp").put(f"{BASE}/pagine/termini",
                                **json_body({"titolo": "X"})).status_code == 403
    assert client_di("anonimo").put(f"{BASE}/pagine/termini",
                                    **json_body({"titolo": "X"})).status_code == 401


# --- Template email ----------------------------------------------------------------

def test_template_lista_dettaglio_salva(client_di):
    c = client_di("segreteria")
    righe = c.get(f"{BASE}/mail").json()
    assert {r["chiave"] for r in righe} >= {"invito_csq", "invito_crp"}
    assert all(r["esiste"] is False for r in righe)

    r = c.get(f"{BASE}/mail/invito_csq")
    assert r.status_code == 200 and "link_attivazione" in r.json()["tag_disponibili"]
    assert c.get(f"{BASE}/mail/chiave_falsa").status_code == 404

    r = c.put(f"{BASE}/mail/invito_csq",
              **json_body({"oggetto": "Ciao", "corpo_html": "<p>{{ nome }}</p>"}))
    assert r.status_code == 200 and r.json()["esiste"] is True
    assert MailTemplate.objects.get(chiave="invito_csq").oggetto == "Ciao"
    assert c.put(f"{BASE}/mail/invito_csq",
                 **json_body({"oggetto": "", "corpo_html": "x"})).status_code == 422


def test_template_importa_copia_elimina(client_di):
    c = client_di("incaricato_eg")
    assert c.post(f"{BASE}/mail/invito_crp/importa").status_code == 201
    assert c.post(f"{BASE}/mail/invito_crp/importa").status_code == 422  # esiste già
    r = c.post(f"{BASE}/mail/invito_crp/copia", **json_body({"target_chiave": "invito_pgv"}))
    assert r.status_code == 201
    assert MailTemplate.objects.filter(chiave="invito_pgv").exists()
    assert c.post(f"{BASE}/mail/invito_crp/copia",
                  **json_body({"target_chiave": "invito_pgv"})).status_code == 422
    assert c.post(f"{BASE}/mail/nessuno/copia",
                  **json_body({"target_chiave": "invito_csq"})).status_code == 404
    # eliminazione solo Admin
    assert c.delete(f"{BASE}/mail/invito_pgv").status_code == 403
    assert client_di("admin").delete(f"{BASE}/mail/invito_pgv").status_code == 204
    assert not MailTemplate.objects.filter(chiave="invito_pgv").exists()


def test_template_vietati(client_di):
    assert client_di("pgv").get(f"{BASE}/mail").status_code == 403
    assert client_di("anonimo").get(f"{BASE}/mail").status_code == 401


def test_upload_immagine_mail(client_di, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    c = client_di("admin")
    img = SimpleUploadedFile("foto.png", b"\x89PNG\r\n", content_type="image/png")
    r = c.post(f"{BASE}/immagini-mail", {"file": img})
    assert r.status_code == 201
    assert "/mail_images/" in r.json()["url"] and r.json()["url"].endswith(".png")
    testo = SimpleUploadedFile("x.txt", b"ciao", content_type="text/plain")
    r = c.post(f"{BASE}/immagini-mail", {"file": testo})
    assert r.status_code == 422 and "file" in r.json()["errori"]
    assert client_di("crp").post(
        f"{BASE}/immagini-mail",
        {"file": SimpleUploadedFile("f.png", b"x", content_type="image/png")},
    ).status_code == 403


# --- Email di test e Gmail OAuth --------------------------------------------------------

def test_email_test(client_di, utenti):
    with mock.patch("apps.siteconfig.services.invia_email_test", return_value="SMTP") as m:
        r = client_di("segreteria").post(f"{BASE}/email/test", **json_body({"backend": "smtp"}))
    assert r.status_code == 200
    m.assert_called_once_with("smtp", utenti["segreteria"].email)
    with mock.patch("apps.siteconfig.services.invia_email_test", side_effect=OSError("giù")):
        r = client_di("segreteria").post(f"{BASE}/email/test", **json_body({}))
    assert r.status_code == 422 and "giù" in r.json()["detail"]
    assert client_di("crp").post(f"{BASE}/email/test", **json_body({})).status_code == 403


@pytest.fixture
def senza_mfa(monkeypatch):
    """La callback è una vista Django: il middleware MFA non deve intervenire nei test."""
    monkeypatch.setattr("apps.accounts.middleware.mfa_da_configurare", lambda request, user: False)


def test_gmail_oauth_avvio_e_callback_spa(client_di, settings, senza_mfa):
    settings.GOOGLE_OAUTH_CLIENT_ID = "id-test"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "segreto-test"
    c = client_di("admin")
    r = c.post(f"{BASE}/email/gmail/oauth")
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("https://accounts.google.com/") and "code_challenge=" in url
    sessione = c.session
    assert sessione["gmail_smtp_oauth_code_verifier"]
    state = sessione["gmail_smtp_oauth_state"]

    with mock.patch("apps.siteconfig.services.completa_oauth_gmail", return_value="a@gmail.com"):
        r = c.get(f"/impostazioni/gmail-smtp/oauth/callback/?state={state}&code=x")
    assert r.status_code == 302
    assert r["Location"].startswith("/impostazioni/email?esito=ok")


def test_gmail_callback_state_non_valido_spa(client_di, senza_mfa):
    c = client_di("admin")
    sessione = c.session
    sessione["gmail_smtp_oauth_state"] = "atteso"
    sessione.save()
    r = c.get("/impostazioni/gmail-smtp/oauth/callback/?state=altro")
    assert r.status_code == 302
    assert r["Location"].startswith("/impostazioni/email?esito=errore")


def test_gmail_disconnetti(client_di, imp):
    from apps.siteconfig.models import GmailSMTPCredenziali

    imp.smtp_use_gmail_oauth = True
    imp.smtp_gmail_account = "a@gmail.com"
    imp.save()
    GmailSMTPCredenziali.objects.create(account_email="a@gmail.com", refresh_token="r")
    r = client_di("incaricato_eg").post(f"{BASE}/email/gmail/disconnetti")
    assert r.status_code == 200
    assert r.json()["email"]["gmail_oauth"] == {"attivo": False, "account": ""}
    assert not GmailSMTPCredenziali.objects.exists()
    assert client_di("csq").post(f"{BASE}/email/gmail/oauth").status_code == 403


# --- Log export, cache PDF, task -------------------------------------------------------

def test_log_export(client_di):
    from apps.exports.models import LogTaskExport

    LogTaskExport.objects.create(tipo=LogTaskExport.Tipo.choices[0][0],
                                 stato=LogTaskExport.Stato.choices[0][0], messaggio="ok")
    r = client_di("segreteria").get(f"{BASE}/log-export")
    assert r.status_code == 200 and r.json()["count"] == 1
    assert client_di("crp").get(f"{BASE}/log-export").status_code == 403


@pytest.fixture
def pdf(diario):
    from apps.storage_drive.models import DriveFile, TipoFile

    return DriveFile.objects.create(drive_file_id="drv-1", nome="tigri.pdf", tipo=TipoFile.PDF,
                                    diario=diario)


def test_cache_pdf_lista_e_invalida(client_di, edizione, pdf):
    c = client_di("admin")
    (ed,) = [e for e in c.get(f"{BASE}/cache-pdf").json() if e["id"] == edizione.pk]
    assert ed["pdf_in_cache"] == 1 and ed["generazione_in_corso"] is False
    files = c.get(f"{BASE}/cache-pdf/file?edizione_id={edizione.pk}").json()
    assert files["count"] == 1 and files["items"][0]["squadriglia"] == "Tigri"
    assert c.delete(f"{BASE}/cache-pdf/file/{pdf.pk}").status_code == 204
    assert c.delete(f"{BASE}/cache-pdf/file/{pdf.pk}").status_code == 404


def test_cache_pdf_invalida_edizione(client_di, edizione, pdf):
    r = client_di("segreteria").post(f"{BASE}/cache-pdf/invalida",
                                     **json_body({"edizione_id": edizione.pk}))
    assert r.status_code == 200 and r.json()["eliminati"] == 1


def test_generazione_massiva_lock(client_di, edizione):
    from apps.exports.tasks import cancel_key_massivo, lock_key_massivo

    c = client_di("incaricato_eg")
    with mock.patch("apps.exports.tasks.task_genera_pdf_massivo.delay") as delay:
        r = c.post(f"{BASE}/cache-pdf/genera", **json_body({"edizione_id": edizione.pk}))
        assert r.status_code == 202
        delay.assert_called_once()
        assert cache.get(lock_key_massivo(edizione.pk))
        # secondo avvio mentre il lock è attivo
        r = c.post(f"{BASE}/cache-pdf/genera", **json_body({"edizione_id": edizione.pk}))
        assert r.status_code == 422
        assert delay.call_count == 1
    cache.set(f"pdf_massivo_task_id:{edizione.pk}", "task-123")
    (ed,) = [e for e in c.get(f"{BASE}/cache-pdf").json() if e["id"] == edizione.pk]
    assert ed["generazione_in_corso"] is True and ed["task_id"] == "task-123"
    assert c.post(f"{BASE}/cache-pdf/interrompi",
                  **json_body({"edizione_id": edizione.pk})).status_code == 202
    assert cache.get(cancel_key_massivo(edizione.pk))
    assert c.post(f"{BASE}/cache-pdf/genera",
                  **json_body({"edizione_id": 999999})).status_code == 404


def test_cache_pdf_vietata(client_di, edizione):
    for ruolo in NON_STAFF:
        assert client_di(ruolo).get(f"{BASE}/cache-pdf").status_code == 403
        assert client_di(ruolo).post(f"{BASE}/cache-pdf/genera",
                                     **json_body({"edizione_id": edizione.pk})).status_code == 403


def test_progresso_task(client_di):
    finto = mock.Mock(state="PROGRESS", info={"progresso": 40, "completati": 4, "totale": 10})
    with mock.patch("celery.result.AsyncResult", return_value=finto):
        r = client_di("admin").get(f"{BASE}/task/abc")
    assert r.json() == {"stato": "PROGRESS", "progresso": 40, "completati": 4, "totale": 10}
    finto = mock.Mock(state="SUCCESS", info=None)
    with mock.patch("celery.result.AsyncResult", return_value=finto):
        assert client_di("admin").get(f"{BASE}/task/abc").json()["progresso"] == 100
    assert client_di("crp").get(f"{BASE}/task/abc").status_code == 403


# --- Axes --------------------------------------------------------------------------

@pytest.fixture
def tentativo(db):
    from axes.models import AccessAttempt

    return AccessAttempt.objects.create(
        ip_address="10.0.0.1", username="x", failures_since_start=5,
        user_agent="t", http_accept="*/*", path_info="/", get_data="", post_data="",
    )


def test_axes_lista_e_sblocco(client_di, tentativo):
    from axes.models import AccessAttempt

    lista = client_di("segreteria").get(f"{BASE}/axes").json()
    assert lista[0]["ip_address"] == "10.0.0.1"
    # sblocco solo Admin
    assert client_di("segreteria").delete(f"{BASE}/axes/{tentativo.pk}").status_code == 403
    assert client_di("admin").delete(f"{BASE}/axes/{tentativo.pk}").status_code == 204
    assert not AccessAttempt.objects.exists()
    assert client_di("admin").delete(f"{BASE}/axes/{tentativo.pk}").status_code == 404


def test_axes_sblocca_tutti(client_di, tentativo):
    assert client_di("incaricato_eg").post(f"{BASE}/axes/sblocca-tutti").status_code == 403
    r = client_di("admin").post(f"{BASE}/axes/sblocca-tutti")
    assert r.status_code == 200 and r.json()["eliminati"] == 1
    assert client_di("crp").get(f"{BASE}/axes").status_code == 403


def test_csrf_richiesto_con_sessione(utenti, imp):
    """Le scritture con cookie di sessione richiedono il token CSRF (come la SPA)."""
    c = Client(enforce_csrf_checks=True)
    c.force_login(utenti["admin"])
    assert c.patch(f"{BASE}/identita", **json_body({"titolo": "X"})).status_code in (401, 403)
