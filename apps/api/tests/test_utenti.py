"""API utenti, profilo, ruoli, sessioni, impersonazione e autocompletamento Socio."""
from __future__ import annotations

import re

import pytest
from django.test import Client

from apps.accounts.models import LoginEvent, Nomina, Ruolo, User
from apps.api.tests.conftest import json_body

pytestmark = pytest.mark.django_db

STAFF = ("admin", "segreteria", "incaricato_eg")
NON_STAFF = ("pgv", "crp", "csq")


@pytest.fixture(autouse=True)
def _senza_rate_limit(monkeypatch):
    """Il rate limit (Redis condiviso, chiave per IP) non è oggetto di questi test."""
    monkeypatch.setattr("apps.siteconfig.middleware._rate_limit_check", lambda *a: (True, 0))


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


def test_me_campi_storici_e_nuovi(client_di, utenti):
    d = client_di("csq").get("/api/v1/me").json()
    for campo in ("id", "email", "nome_completo", "ruolo", "ruoli_attivi",
                  "is_staff_plancia", "is_superuser"):
        assert campo in d
    assert d["socio"]["codice_socio"] == "700005"
    assert d["socio"]["categoria"] == "ragazzo"
    assert d["mfa_attiva"] is False
    assert d["mfa_richiesta"] is False
    assert d["impersonato_da"] is None
    assert d["puo_modificare_email"] is True
    assert d["menu"]["puo_vedere_diari"] is True
    assert d["menu"]["puo_vedere_utenti"] is False
    assert d["menu"]["puo_vedere_impostazioni"] is False


@pytest.mark.parametrize(("ruolo", "utenti_", "impostazioni", "statistiche"), [
    ("admin", True, True, True),
    ("segreteria", True, False, False),
    ("incaricato_eg", True, False, True),
    ("pgv", False, False, False),
    ("crp", False, False, False),
])
def test_me_flag_menu(client_di, ruolo, utenti_, impostazioni, statistiche):
    menu = client_di(ruolo).get("/api/v1/me").json()["menu"]
    assert menu["puo_vedere_utenti"] is utenti_
    assert menu["puo_gestire_edizioni"] is utenti_
    assert menu["puo_importare"] is utenti_
    assert menu["puo_vedere_impostazioni"] is impostazioni
    assert menu["puo_vedere_statistiche"] is statistiche
    assert menu["puo_gestire_inviti_crp"] is (ruolo == "crp")


def test_me_mfa_richiesta_admin(client_di, utenti, settings):
    from allauth.mfa.models import Authenticator

    settings.DEBUG = False
    settings.SKIP_MFA_ENFORCEMENT = False
    Authenticator.objects.filter(user=utenti["admin"]).delete()
    d = client_di("admin").get("/api/v1/me").json()
    assert d["mfa_richiesta"] is True
    assert d["mfa_attiva"] is False
    assert d["mfa_da_configurare"] is True
    assert d["socio"] is None


# ---------------------------------------------------------------------------
# PATCH /me, profilo, nomine, accessi
# ---------------------------------------------------------------------------


def test_patch_me_email_csq(client_di, utenti):
    r = client_di("csq").patch("/api/v1/me", **json_body({"email": "nuova@test.it"}))
    assert r.status_code == 200
    assert r.json()["email"] == "nuova@test.it"
    u = User.objects.get(pk=utenti["csq"].pk)
    assert u.email == "nuova@test.it"
    assert u.socio.email == "nuova@test.it"


def test_patch_me_email_duplicata(client_di):
    r = client_di("csq").patch("/api/v1/me", **json_body({"email": "crp@test.it"}))
    assert r.status_code == 422
    assert "email" in r.json()["errori"]


def test_patch_me_email_vuota(client_di):
    r = client_di("csq").patch("/api/v1/me", **json_body({"email": "  "}))
    assert r.status_code == 422


@pytest.mark.parametrize("ruolo", ["crp", "admin", "segreteria"])
def test_patch_me_email_non_csq(client_di, ruolo):
    r = client_di(ruolo).patch("/api/v1/me", **json_body({"email": "x@test.it"}))
    assert r.status_code == 403


def test_patch_me_anonimo(client_di):
    r = client_di("anonimo").patch("/api/v1/me", **json_body({"email": "x@test.it"}))
    assert r.status_code == 401


def test_profilo(client_di, utenti):
    LoginEvent.objects.create(utente=utenti["crp"], ip="10.0.0.1", esito="login")
    d = client_di("crp").get("/api/v1/me/profilo").json()
    assert d["utente"]["id"] == utenti["crp"].pk
    assert [n["ruolo"]["chiave"] for n in d["nomine"]] == ["crp"]
    assert d["accessi"][0]["ip"] == "10.0.0.1"
    assert d["accessi"][0]["provider"] == "email"
    assert d["social_accounts"] == []


def test_profilo_anonimo(client_di):
    assert client_di("anonimo").get("/api/v1/me/profilo").status_code == 401


def test_mie_nomine_e_accessi(client_di, utenti):
    LoginEvent.objects.create(utente=utenti["pgv"], esito="login")
    LoginEvent.objects.create(utente=utenti["crp"], esito="login")  # di un altro
    c = client_di("pgv")
    assert len(c.get("/api/v1/me/nomine").json()) == 1
    acc = c.get("/api/v1/me/accessi").json()
    assert acc["count"] == 1


# ---------------------------------------------------------------------------
# POST /me/ruolo
# ---------------------------------------------------------------------------


def test_cambia_ruolo(client_di, utenti):
    u = utenti["crp"]
    Nomina.objects.create(utente=u, ruolo=Ruolo.PGV, socio=u.socio)
    r = client_di("crp").post("/api/v1/me/ruolo", **json_body({"ruolo": "pgv"}))
    assert r.status_code == 200
    assert r.json()["ruolo"]["chiave"] == "pgv"
    u.refresh_from_db()
    assert u.ruolo == "pgv"


def test_cambia_ruolo_non_posseduto(client_di, utenti):
    r = client_di("crp").post("/api/v1/me/ruolo", **json_body({"ruolo": "admin"}))
    assert r.status_code == 422
    utenti["crp"].refresh_from_db()
    assert utenti["crp"].ruolo == "crp"


def test_cambia_ruolo_nomina_revocata(client_di, utenti):
    u = utenti["crp"]
    Nomina.objects.create(utente=u, ruolo=Ruolo.PGV, socio=u.socio, attiva=False)
    r = client_di("crp").post("/api/v1/me/ruolo", **json_body({"ruolo": "pgv"}))
    assert r.status_code == 422


def test_cambia_ruolo_anonimo(client_di):
    r = client_di("anonimo").post("/api/v1/me/ruolo", **json_body({"ruolo": "pgv"}))
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Sessioni
# ---------------------------------------------------------------------------


def _sessione_allauth(user, session_key: str):
    from allauth.usersessions.models import UserSession

    return UserSession.objects.create(user=user, ip="10.0.0.9", session_key=session_key,
                                      user_agent="test")


def test_sessioni_e_termina_altre(client_di, utenti):
    from allauth.usersessions.models import UserSession
    from django.contrib.sessions.backends.db import SessionStore

    c = client_di("crp")
    corrente = c.session.session_key
    _sessione_allauth(utenti["crp"], corrente)
    # un'altra sessione reale dello stesso utente
    altro = Client()
    altro.force_login(utenti["crp"])
    _sessione_allauth(utenti["crp"], altro.session.session_key)
    # una sessione di un altro utente: non va toccata
    terzo = Client()
    terzo.force_login(utenti["pgv"])
    _sessione_allauth(utenti["pgv"], terzo.session.session_key)

    lista = c.get("/api/v1/me/sessioni").json()
    assert len(lista) == 2
    assert sum(s["corrente"] for s in lista) == 1

    r = c.post("/api/v1/me/sessioni/termina-altre")
    assert r.status_code == 200
    assert r.json()["terminate"] == 1
    assert not SessionStore().exists(altro.session.session_key)
    assert UserSession.objects.filter(user=utenti["crp"]).count() == 1
    assert UserSession.objects.filter(user=utenti["pgv"]).count() == 1
    assert altro.get("/api/v1/me").status_code == 401
    assert c.get("/api/v1/me").status_code == 200


def test_termina_altre_nessuna(client_di):
    r = client_di("csq").post("/api/v1/me/sessioni/termina-altre")
    assert r.json()["terminate"] == 0


def test_sessioni_anonimo(client_di):
    assert client_di("anonimo").get("/api/v1/me/sessioni").status_code == 401
    assert client_di("anonimo").post("/api/v1/me/sessioni/termina-altre").status_code == 401


# ---------------------------------------------------------------------------
# Impersonazione
# ---------------------------------------------------------------------------


def test_impersona_e_termina(client_di, utenti):
    from hijack import signals

    eventi = []

    def _ricevi(sender, **kw):
        eventi.append((kw["hijacker"].pk, kw["hijacked"].pk))

    signals.hijack_started.connect(_ricevi)
    signals.hijack_ended.connect(_ricevi)
    try:
        c = client_di("segreteria")
        r = c.post(f"/api/v1/utenti/{utenti['csq'].pk}/impersona")
        assert r.status_code == 200, r.content
        d = r.json()
        assert d["id"] == utenti["csq"].pk
        assert d["impersonato_da"]["id"] == utenti["segreteria"].pk
        me = c.get("/api/v1/me").json()
        assert me["id"] == utenti["csq"].pk
        assert me["impersonato_da"]["id"] == utenti["segreteria"].pk
        assert me["mfa_da_configurare"] is False

        r = c.post("/api/v1/me/impersonazione/termina")
        assert r.status_code == 200
        assert r.json()["id"] == utenti["segreteria"].pk
        assert r.json()["impersonato_da"] is None
        assert c.get("/api/v1/me").json()["id"] == utenti["segreteria"].pk
    finally:
        signals.hijack_started.disconnect(_ricevi)
        signals.hijack_ended.disconnect(_ricevi)
    assert eventi == [(utenti["segreteria"].pk, utenti["csq"].pk)] * 2


def test_segreteria_non_impersona_chi_ha_nomina_admin(client_di, utenti):
    u = utenti["crp"]
    Nomina.objects.create(utente=u, ruolo=Ruolo.ADMIN)
    r = client_di("segreteria").post(f"/api/v1/utenti/{u.pk}/impersona")
    assert r.status_code == 403
    assert client_di("segreteria").post(
        f"/api/v1/utenti/{utenti['admin'].pk}/impersona").status_code == 403


def test_admin_impersona_segreteria(client_di, utenti):
    r = client_di("admin").post(f"/api/v1/utenti/{utenti['segreteria'].pk}/impersona")
    assert r.status_code == 200


@pytest.mark.parametrize("ruolo", ["incaricato_eg", "crp", "csq"])
def test_impersona_ruoli_non_ammessi(client_di, utenti, ruolo):
    r = client_di(ruolo).post(f"/api/v1/utenti/{utenti['estraneo'].pk}/impersona")
    assert r.status_code == 403


def test_impersona_anonimo_e_inesistente(client_di):
    assert client_di("anonimo").post("/api/v1/utenti/1/impersona").status_code == 401
    assert client_di("admin").post("/api/v1/utenti/999999/impersona").status_code == 404


def test_termina_impersonazione_senza_impersonazione(client_di):
    assert client_di("admin").post("/api/v1/me/impersonazione/termina").status_code == 422


# ---------------------------------------------------------------------------
# /utenti: lista, opzioni, dettaglio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ruolo", STAFF)
def test_lista_utenti_staff(client_di, ruolo):
    r = client_di(ruolo).get("/api/v1/utenti")
    assert r.status_code == 200
    assert r.json()["count"] == User.objects.count()


@pytest.mark.parametrize("ruolo", NON_STAFF)
def test_lista_utenti_non_staff(client_di, ruolo):
    assert client_di(ruolo).get("/api/v1/utenti").status_code == 403


def test_lista_utenti_anonimo(client_di):
    assert client_di("anonimo").get("/api/v1/utenti").status_code == 401


def test_lista_utenti_filtri(client_di):
    c = client_di("segreteria")
    d = c.get("/api/v1/utenti?ruolo=csq").json()
    assert d["count"] == User.objects.filter(ruolo="csq").count()
    assert {u["ruolo"]["chiave"] for u in d["items"]} == {"csq"}
    d = c.get("/api/v1/utenti?q=Incaricato").json()  # nome del socio
    assert [u["email"] for u in d["items"]] == ["incaricato_eg@test.it"]
    d = c.get("/api/v1/utenti?q=pgv@").json()  # email
    assert d["count"] == 1
    d = c.get("/api/v1/utenti?limit=3").json()
    assert len(d["items"]) == 3


def test_opzioni_per_ruolo(client_di):
    seg = client_di("segreteria").get("/api/v1/utenti/opzioni").json()
    chiavi = {r["chiave"] for r in seg["ruoli_nominabili"]}
    assert chiavi == {"incaricato_eg", "pgv", "crp", "csq"}
    assert "csq" not in {r["chiave"] for r in seg["ruoli_nominabili_da_socio"]}
    assert {r["chiave"] for r in seg["ruoli_staff_creabili"]} == {"incaricato_eg"}
    assert seg["puo_impersonare"] is True
    iabr = client_di("incaricato_eg").get("/api/v1/utenti/opzioni").json()
    assert iabr["ruoli_staff_creabili"] == []
    assert iabr["puo_impersonare"] is False
    assert client_di("crp").get("/api/v1/utenti/opzioni").status_code == 403


def test_dettaglio_utente(client_di, utenti):
    LoginEvent.objects.create(utente=utenti["crp"], esito="fallito")
    d = client_di("incaricato_eg").get(f"/api/v1/utenti/{utenti['crp'].pk}").json()
    assert d["socio"]["codice_socio"] == "700004"
    assert d["nomine"][0]["ruolo"]["chiave"] == "crp"
    assert d["accessi"][0]["esito"] == "fallito"
    assert d["puo_impersonare"] is False
    d = client_di("segreteria").get(f"/api/v1/utenti/{utenti['crp'].pk}").json()
    assert d["puo_impersonare"] is True


def test_dettaglio_permessi(client_di, utenti):
    assert client_di("crp").get(f"/api/v1/utenti/{utenti['csq'].pk}").status_code == 403
    assert client_di("anonimo").get(f"/api/v1/utenti/{utenti['csq'].pk}").status_code == 401
    assert client_di("admin").get("/api/v1/utenti/999999").status_code == 404


# ---------------------------------------------------------------------------
# Nomine
# ---------------------------------------------------------------------------


def test_nomina_pgv_da_incaricato(client_di, utenti):
    u = utenti["crp"]
    r = client_di("incaricato_eg").post(
        f"/api/v1/utenti/{u.pk}/nomine", **json_body({"ruolo": "pgv", "scadenza": "2099-12-31"}))
    assert r.status_code == 201, r.content
    assert r.json()["ruolo"]["chiave"] == "pgv"
    assert r.json()["scadenza"] == "2099-12-31"
    assert "pgv" in u.ruoli_attivi


def test_nomina_ruolo_non_consentito(client_di, utenti):
    r = client_di("incaricato_eg").post(
        f"/api/v1/utenti/{utenti['crp'].pk}/nomine", **json_body({"ruolo": "segreteria"}))
    assert r.status_code == 403


def test_nomina_categoria_incompatibile(client_di, utenti):
    r = client_di("admin").post(
        f"/api/v1/utenti/{utenti['csq'].pk}/nomine", **json_body({"ruolo": "crp"}))
    assert r.status_code == 422


def test_nomina_esclusivita_csq(client_di, utenti, edizione):
    u = utenti["csq"]
    Nomina.objects.create(utente=u, ruolo=Ruolo.PGV, edizione=edizione)
    r = client_di("admin").post(
        f"/api/v1/utenti/{u.pk}/nomine",
        **json_body({"ruolo": "csq", "edizione_id": edizione.pk}))
    assert r.status_code == 422
    assert "stessa edizione" in r.json()["errori"]["__all__"][0]


def test_nomina_dati_non_validi(client_di, utenti):
    c = client_di("admin")
    url = f"/api/v1/utenti/{utenti['crp'].pk}/nomine"
    assert c.post(url, **json_body({"ruolo": "boh"})).status_code == 422
    assert c.post(url, **json_body({"ruolo": "pgv", "edizione_id": 999999})).status_code == 422


@pytest.mark.parametrize("ruolo", NON_STAFF)
def test_nomina_non_staff(client_di, utenti, ruolo):
    r = client_di(ruolo).post(
        f"/api/v1/utenti/{utenti['estraneo'].pk}/nomine", **json_body({"ruolo": "csq"}))
    assert r.status_code == 403


def test_revoca_nomina(client_di, utenti):
    u = utenti["crp"]
    n = Nomina.objects.create(utente=u, ruolo=Ruolo.PGV, socio=u.socio)
    u.ruolo = Ruolo.PGV
    u.save(update_fields=["ruolo"])
    r = client_di("incaricato_eg").post(f"/api/v1/utenti/{u.pk}/nomine/{n.pk}/revoca")
    assert r.status_code == 200
    assert r.json()["attiva"] is False
    n.refresh_from_db()
    u.refresh_from_db()
    assert n.attiva is False
    assert u.ruolo == Ruolo.CRP  # torna al ruolo rimasto


def test_revoca_nomina_regole(client_di, utenti):
    seg = utenti["segreteria"]
    n_seg = Nomina.objects.get(utente=seg, ruolo=Ruolo.SEGRETERIA)
    # l'Incaricato non può revocare la Segreteria
    assert client_di("incaricato_eg").post(
        f"/api/v1/utenti/{seg.pk}/nomine/{n_seg.pk}/revoca").status_code == 403
    # nomina da Sestante
    sso = Nomina.objects.create(utente=utenti["crp"], ruolo=Ruolo.SEGRETERIA, da_sso=True)
    assert client_di("admin").post(
        f"/api/v1/utenti/{utenti['crp'].pk}/nomine/{sso.pk}/revoca").status_code == 422
    # propria nomina
    n_admin = Nomina.objects.get(utente=utenti["admin"])
    assert client_di("admin").post(
        f"/api/v1/utenti/{utenti['admin'].pk}/nomine/{n_admin.pk}/revoca").status_code == 422
    # nomina di un altro utente rispetto al percorso
    assert client_di("admin").post(
        f"/api/v1/utenti/{utenti['crp'].pk}/nomine/{n_seg.pk}/revoca").status_code == 404
    assert client_di("crp").post(
        f"/api/v1/utenti/{seg.pk}/nomine/{n_seg.pk}/revoca").status_code == 403


# ---------------------------------------------------------------------------
# Creazione utenti
# ---------------------------------------------------------------------------


def test_crea_staff_segreteria_crea_incaricato(client_di, mailoutbox):
    r = client_di("segreteria").post("/api/v1/utenti/staff", **json_body({
        "email": "Nuovo.Iabr@Test.it", "first_name": "Nuovo", "last_name": "Iabr",
        "ruolo": "incaricato_eg",
    }))
    assert r.status_code == 201, r.content
    d = r.json()
    assert d["creato"] is True
    assert d["utente"]["email"] == "nuovo.iabr@test.it"
    assert d["nomina"]["ruolo"]["chiave"] == "incaricato_eg"
    u = User.objects.get(email="nuovo.iabr@test.it")
    assert not u.has_usable_password()
    assert u.ruolo == "incaricato_eg"
    # Email di allauth con il link alla pagina della SPA per impostare la password
    assert "inviata un'email" in d["detail"]
    assert len(mailoutbox) == 1
    msg = mailoutbox[0]
    assert msg.to == ["nuovo.iabr@test.it"]
    corpo = msg.body + "".join(str(a[0]) for a in getattr(msg, "alternatives", []))
    m = re.search(r"https?://[^/\s\"]+/password/reset/([^\s\"<]+)", corpo)
    assert m, corpo
    # La chiave è valida per il reset headless (pagina /password/reset/{key} della SPA)
    anonimo = Client()
    r = anonimo.get("/_allauth/browser/v1/auth/password/reset", HTTP_X_PASSWORD_RESET_KEY=m.group(1))
    assert r.status_code == 200, r.content
    r = anonimo.post("/_allauth/browser/v1/auth/password/reset", **json_body(
        {"key": m.group(1), "password": "Nuova-Password-Lunga-42"}))
    assert r.status_code in (200, 401), r.content  # 401: password impostata, serve il login
    u.refresh_from_db()
    assert u.check_password("Nuova-Password-Lunga-42")


def test_crea_staff_errore_email_segnalato(client_di, caplog):
    from unittest import mock

    with mock.patch(
        "allauth.account.internal.flows.password_reset.request_password_reset",
        side_effect=RuntimeError("smtp giù"),
    ):
        r = client_di("admin").post("/api/v1/utenti/staff", **json_body({
            "email": "senza.mail@test.it", "ruolo": "incaricato_eg",
        }))
    assert r.status_code == 201, r.content
    assert "Non è stato possibile inviare" in r.json()["detail"]
    assert "smtp giù" in caplog.text


def test_crea_staff_regole(client_di, utenti):
    c = client_di("segreteria")
    assert c.post("/api/v1/utenti/staff", **json_body(
        {"email": "x@test.it", "ruolo": "segreteria"})).status_code == 422
    assert c.post("/api/v1/utenti/staff", **json_body(
        {"email": "", "ruolo": "incaricato_eg"})).status_code == 422
    # utente già esistente con ruoli attivi
    assert client_di("admin").post("/api/v1/utenti/staff", **json_body(
        {"email": "crp@test.it", "ruolo": "incaricato_eg"})).status_code == 422
    assert client_di("incaricato_eg").post("/api/v1/utenti/staff", **json_body(
        {"email": "y@test.it", "ruolo": "incaricato_eg"})).status_code == 422
    assert client_di("crp").post("/api/v1/utenti/staff", **json_body(
        {"email": "y@test.it", "ruolo": "incaricato_eg"})).status_code == 403
    assert client_di("anonimo").post("/api/v1/utenti/staff", **json_body(
        {"email": "y@test.it", "ruolo": "incaricato_eg"})).status_code == 401


def test_crea_da_socio(client_di, org):
    from apps.org.models import Socio

    s = Socio.objects.create(codice_socio="800001", nome="Nuovo", cognome="Capo",
                             email="nuovo.capo@test.it", categoria="capo",
                             zona=org["zona"], gruppo=org["gruppo"])
    r = client_di("incaricato_eg").post("/api/v1/utenti/da-socio",
                                        **json_body({"socio_id": s.pk, "ruolo": "crp"}))
    assert r.status_code == 201, r.content
    d = r.json()
    assert d["creato"] is True
    assert d["utente"]["socio"]["id"] == s.pk
    assert d["nomina"]["ruolo"]["chiave"] == "crp"
    assert User.objects.get(socio=s).ruolo == "crp"


def test_crea_da_socio_regole(client_di, utenti):
    ragazzo = utenti["estraneo"].socio
    capo = utenti["pgv"].socio
    c = client_di("incaricato_eg")
    # socio ragazzo: non è un capo
    assert c.post("/api/v1/utenti/da-socio", **json_body(
        {"socio_id": ragazzo.pk, "ruolo": "crp"})).status_code == 422
    # ruolo non assegnabile dall'Incaricato
    assert c.post("/api/v1/utenti/da-socio", **json_body(
        {"socio_id": capo.pk, "ruolo": "segreteria"})).status_code == 403
    # capo come Capo Squadriglia: categoria incompatibile
    assert c.post("/api/v1/utenti/da-socio", **json_body(
        {"socio_id": capo.pk, "ruolo": "csq"})).status_code == 422
    assert client_di("crp").post("/api/v1/utenti/da-socio", **json_body(
        {"socio_id": capo.pk, "ruolo": "crp"})).status_code == 403


# ---------------------------------------------------------------------------
# /org/soci
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ruolo", STAFF)
def test_soci_staff(client_di, ruolo):
    r = client_di(ruolo).get("/api/v1/org/soci?q=Test&categoria=capo")
    assert r.status_code == 200
    d = r.json()
    assert {s["categoria"] for s in d} == {"capo"}
    assert len(d) == 4
    assert d[0]["label"].endswith(f"#{d[0]['codice_socio']}")


def test_soci_filtri(client_di, utenti):
    c = client_di("admin")
    d = c.get("/api/v1/org/soci?q=70000").json()
    assert len(d) == 6
    d = c.get("/api/v1/org/soci?q=700003").json()
    assert d[0]["user_pk"] == utenti["pgv"].pk
    d = c.get("/api/v1/org/soci?ruolo=crp").json()
    assert [s["codice_socio"] for s in d] == ["700004"]


def test_soci_crp_solo_ragazzi(client_di):
    d = client_di("crp").get("/api/v1/org/soci?q=Test&categoria=capo").json()
    assert d and {s["categoria"] for s in d} == {"ragazzo"}


@pytest.mark.parametrize("ruolo", ["csq", "pgv"])
def test_soci_ruoli_non_ammessi(client_di, ruolo):
    assert client_di(ruolo).get("/api/v1/org/soci?q=Test").status_code == 403


def test_soci_anonimo(client_di):
    assert client_di("anonimo").get("/api/v1/org/soci?q=Test").status_code == 401


def test_impersona_con_csrf_come_la_spa(utenti):
    """Con i controlli CSRF attivi (browser reale) serve l'header X-CSRFToken."""
    from django.middleware.csrf import _get_new_csrf_string

    c = Client(enforce_csrf_checks=True)
    c.force_login(utenti["admin"])
    url = f"/api/v1/utenti/{utenti['crp'].pk}/impersona"
    assert c.post(url).status_code == 403
    token = _get_new_csrf_string()
    c.cookies["csrftoken"] = token
    r = c.post(url, HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 200
    assert r.json()["impersonato_da"]["id"] == utenti["admin"].pk


def test_impersona_rifiutata_con_session_token(client_di, utenti):
    r = client_di("admin").post(f"/api/v1/utenti/{utenti['crp'].pk}/impersona",
                                HTTP_X_SESSION_TOKEN="qualcosa")
    assert r.status_code in (401, 422)
