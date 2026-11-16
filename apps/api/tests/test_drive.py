"""API Google Drive: avvio OAuth, callback → SPA, stato, picker cartelle, cartelle dell'edizione.

Le chiamate a Google sono simulate (`_build_drive_service`, `Flow`, `build`).
"""
from __future__ import annotations

from unittest import mock

import pytest

from apps.api.tests.conftest import json_body
from apps.storage_drive.models import DriveCredenziali

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _senza_rate_limit():
    """Il rate limit API conta su Redis per IP (condiviso tra i test): qui non interessa."""
    with mock.patch("apps.siteconfig.middleware._rate_limit_check", return_value=(True, 0)):
        yield

ACCOUNT = "drive@test.it"


@pytest.fixture(autouse=True)
def _senza_mfa(settings):
    """Le viste web (callback) passano dal middleware MFA: qui non interessa."""
    settings.SKIP_MFA_ENFORCEMENT = True


@pytest.fixture
def credenziali(db):
    return DriveCredenziali.objects.create(account_email=ACCOUNT, access_token="a",
                                           refresh_token="r")


@pytest.fixture
def oauth_settings(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "client-secret"
    settings.GOOGLE_OAUTH_REDIRECT_URI = "http://testserver/drive/oauth/callback/"
    return settings


@pytest.fixture
def servizio():
    """Client Drive finto restituito da `_build_drive_service`."""
    s = mock.MagicMock()
    with mock.patch("apps.storage_drive.service._build_drive_service", return_value=s):
        yield s


# --- OAuth ------------------------------------------------------------------------

def test_avvio_oauth_restituisce_url_e_salva_pkce(client_di, edizione, oauth_settings):
    c = client_di("segreteria")
    flow = mock.MagicMock()
    flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?x=1", "st")
    with mock.patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=flow):
        r = c.post("/api/v1/drive/oauth", **json_body({"edizione_id": edizione.pk}))
    assert r.status_code == 200
    assert r.json() == {"url": "https://accounts.google.com/o/oauth2/auth?x=1"}
    kwargs = flow.authorization_url.call_args.kwargs
    assert kwargs["code_challenge_method"] == "S256" and kwargs["code_challenge"]
    sessione = c.session
    assert sessione["drive_oauth_state"] == "st"
    assert sessione["drive_oauth_edizione"] == str(edizione.pk)
    assert sessione["drive_oauth_code_verifier"]


def test_avvio_oauth_permessi_e_errori(client_di, edizione, oauth_settings):
    assert client_di("crp").post("/api/v1/drive/oauth", **json_body({})).status_code == 403
    assert client_di("anonimo").post("/api/v1/drive/oauth", **json_body({})).status_code == 401
    assert client_di("admin").post("/api/v1/drive/oauth",
                                   **json_body({"edizione_id": 999999})).status_code == 404
    oauth_settings.GOOGLE_OAUTH_CLIENT_ID = ""
    assert client_di("admin").post("/api/v1/drive/oauth", **json_body({})).status_code == 422


def _prepara_sessione(c, edizione_pk="", state="st"):
    s = c.session
    s["drive_oauth_state"] = state
    s["drive_oauth_edizione"] = str(edizione_pk)
    s["drive_oauth_code_verifier"] = "verifier"
    s.save()


def test_callback_reindirizza_alla_spa_edizione(client_di, edizione, oauth_settings):
    c = client_di("incaricato_eg")
    _prepara_sessione(c, edizione.pk)
    flow = mock.MagicMock()
    flow.credentials.token = "tok"
    flow.credentials.refresh_token = "ref"
    flow.credentials.expiry = None
    oauth2 = mock.MagicMock()
    oauth2.userinfo.return_value.get.return_value.execute.return_value = {"email": ACCOUNT}
    with mock.patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=flow), \
            mock.patch("googleapiclient.discovery.build", return_value=oauth2):
        r = c.get("/drive/oauth/callback/?state=st&code=abc")
    assert r.status_code == 302
    assert r.url.startswith(f"/edizioni/{edizione.pk}?drive=ok")
    flow.fetch_token.assert_called_once()
    assert flow.fetch_token.call_args.kwargs["code_verifier"] == "verifier"
    edizione.refresh_from_db()
    assert edizione.drive_oauth_account == ACCOUNT
    assert DriveCredenziali.objects.get(account_email=ACCOUNT).refresh_token == "ref"


def test_callback_state_non_valido(client_di, edizione):
    c = client_di("incaricato_eg")
    _prepara_sessione(c, edizione.pk, state="giusto")
    r = c.get("/drive/oauth/callback/?state=sbagliato&code=abc")
    assert r.status_code == 302 and r.url.startswith(f"/edizioni/{edizione.pk}?drive=errore")
    r = client_di("admin").get("/drive/oauth/callback/?state=x")
    assert r.status_code == 302 and r.url.startswith("/impostazioni/drive?esito=errore")


def test_callback_scambio_fallito(client_di, oauth_settings):
    c = client_di("admin")
    _prepara_sessione(c)
    flow = mock.MagicMock()
    flow.fetch_token.side_effect = RuntimeError("invalid_grant")
    with mock.patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=flow):
        r = c.get("/drive/oauth/callback/?state=st&code=abc")
    assert r.status_code == 302 and r.url.startswith("/impostazioni/drive?esito=errore")
    assert not DriveCredenziali.objects.exists()


def test_stato(client_di, credenziali, oauth_settings):
    r = client_di("incaricato_eg").get("/api/v1/drive/stato")
    assert r.status_code == 200
    dati = r.json()
    assert dati["oauth_configurato"] is True
    assert dati["account"][0]["email"] == ACCOUNT
    assert "access_token" not in str(dati)
    assert client_di("pgv").get("/api/v1/drive/stato").status_code == 403


# --- Picker -----------------------------------------------------------------------

def test_elenca_cartelle(client_di, credenziali, servizio):
    servizio.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "f1", "name": "Allegati"}]
    }
    r = client_di("admin").get(f"/api/v1/drive/cartelle?account={ACCOUNT}&q=All'")
    assert r.status_code == 200 and r.json() == [{"id": "f1", "nome": "Allegati"}]
    q = servizio.files.return_value.list.call_args.kwargs["q"]
    assert "name contains 'All'" in q  # apice rimosso
    assert client_di("crp").get(f"/api/v1/drive/cartelle?account={ACCOUNT}").status_code == 403
    assert client_di("admin").get("/api/v1/drive/cartelle?account=x@y.it").status_code == 404


def test_elenca_cartelle_errore_google(client_di, credenziali, servizio):
    servizio.files.return_value.list.return_value.execute.side_effect = RuntimeError("quota")
    r = client_di("admin").get(f"/api/v1/drive/cartelle?account={ACCOUNT}")
    assert r.status_code == 502


def test_crea_cartella(client_di, credenziali, servizio):
    servizio.files.return_value.create.return_value.execute.return_value = {"id": "nuova"}
    c = client_di("segreteria")
    r = c.post("/api/v1/drive/cartelle", **json_body({"account": ACCOUNT, "nome": " GV 2098 ",
                                                       "parent_id": "root1"}))
    assert r.status_code == 201 and r.json() == {"id": "nuova", "nome": "GV 2098"}
    body = servizio.files.return_value.create.call_args.kwargs["body"]
    assert body["parents"] == ["root1"]
    assert c.post("/api/v1/drive/cartelle",
                  **json_body({"account": ACCOUNT, "nome": " "})).status_code == 422
    assert client_di("csq").post("/api/v1/drive/cartelle",
                                 **json_body({"account": ACCOUNT, "nome": "x"})).status_code == 403


def test_info_cartella(client_di, credenziali, servizio):
    servizio.files.return_value.get.return_value.execute.return_value = {
        "id": "f1", "name": "Output", "webViewLink": "https://drive.google.com/f1"}
    r = client_di("admin").get(f"/api/v1/drive/cartelle/f1?account={ACCOUNT}")
    assert r.status_code == 200
    assert r.json() == {"id": "f1", "nome": "Output", "url": "https://drive.google.com/f1"}


# --- Cartelle dell'edizione -----------------------------------------------------------

def test_cartelle_edizione_salva_e_blocca(client_di, edizione, credenziali):
    edizione.drive_oauth_account = ACCOUNT
    edizione.save()
    c = client_di("incaricato_eg")
    url = f"/api/v1/drive/edizioni/{edizione.pk}"
    dati = c.get(url).json()
    assert dati["account_collegato"] is True and dati["cartelle_configurate"] is False

    r = c.put(url, **json_body({"drive_folder_allegati_id": "a1", "drive_folder_output_id": "",
                                "cartella_diario_format": "{nome_squadriglia}"}))
    assert r.status_code == 422 and "cartella_diario_format" in r.json()["errori"]

    r = c.put(url, **json_body({"drive_folder_allegati_id": "a1", "drive_folder_output_id": "o1",
                                "cartella_diario_format": "{id_univoco}_{nome_squadriglia}"}))
    assert r.status_code == 200 and r.json()["cartelle_configurate"] is True

    r = c.put(url, **json_body({"drive_folder_allegati_id": "altro", "drive_folder_output_id": "o2"}))
    assert r.status_code == 422
    edizione.refresh_from_db()
    assert edizione.drive_folder_allegati_id == "a1"
    assert client_di("crp").get(url).status_code == 403
    assert client_di("admin").get("/api/v1/drive/edizioni/999999").status_code == 404


def test_vista_web_cartelle_bloccate(client_di, edizione, settings):
    settings.SKIP_MFA_ENFORCEMENT = True
    edizione.drive_folder_allegati_id = "a1"
    edizione.drive_folder_output_id = "o1"
    edizione.save()  # il formato ha già il default → configurazione bloccata
    r = client_di("admin").post(f"/drive/edizione/{edizione.pk}/cartelle/",
                                {"drive_folder_allegati_id": "x", "drive_folder_output_id": "y"})
    assert r.status_code == 302
    edizione.refresh_from_db()
    assert edizione.drive_folder_allegati_id == "a1"
