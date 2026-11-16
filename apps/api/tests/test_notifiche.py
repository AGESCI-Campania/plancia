"""API notifiche: gestione inviti, inviti del Capo Reparto, reinvio, attivazione account."""

import pytest
from django.test import Client

from apps.accounts.models import Nomina, Ruolo, User
from apps.api.tests.conftest import json_body
from apps.notifications.models import Invito, StatoInvito, TipoInvito

pytestmark = pytest.mark.django_db

BASE = "/api/v1/notifiche"


@pytest.fixture(autouse=True)
def senza_rate_limit(monkeypatch):
    """Il contatore del rate limit (cache del processo) non deve accumularsi tra i test."""
    monkeypatch.setattr("apps.siteconfig.middleware._rate_limit_check", lambda *a, **k: (True, 0))


@pytest.fixture(autouse=True)
def niente_celery(monkeypatch):
    """Nessun task reale: registra le chiamate a .delay."""
    chiamate: dict[str, list] = {}

    def finto(nome):
        def _delay(*args, **kwargs):
            chiamate.setdefault(nome, []).append((args, kwargs))
        return _delay

    from apps.notifications import tasks

    for nome in ("task_invia_invito", "task_invia_inviti_bulk",
                 "task_invia_inviti_capi_edizione", "task_invia_inviti_csq_edizione"):
        monkeypatch.setattr(getattr(tasks, nome), "delay", finto(nome))
    return chiamate


@pytest.fixture
def invito_csq(diario, utenti):
    return Invito.objects.create(
        diario=diario, utente=utenti["csq"], ruolo_target=Ruolo.CSQ, tipo=TipoInvito.CODICE_SOCIO,
    )


@pytest.fixture
def invito_crp(diario, utenti):
    return Invito.objects.create(
        diario=diario, utente=utenti["crp"], ruolo_target=Ruolo.CRP, tipo=TipoInvito.STANDARD,
    )


# --- Gestione inviti (staff) -------------------------------------------------

@pytest.mark.parametrize("ruolo", ["admin", "segreteria", "incaricato_eg"])
def test_lista_inviti_staff(client_di, invito_csq, invito_crp, ruolo):
    r = client_di(ruolo).get(f"{BASE}/inviti")
    assert r.status_code == 200
    righe = r.json()["items"]
    assert len(righe) == 1
    riga = righe[0]
    assert riga["squadriglia"] == "Tigri"
    assert riga["ultimo_invito_csq"]["id"] == invito_csq.pk
    assert riga["ultimo_invito_crp"]["id"] == invito_crp.pk
    assert riga["ultimo_invito_csq"]["delivery_status"] == "in_attesa"
    assert set(riga["inviti_reinviabili"]) == {invito_csq.pk, invito_crp.pk}


def test_lista_inviti_filtri(client_di, invito_csq):
    c = client_di("segreteria")
    assert c.get(f"{BASE}/inviti?zona=Zona API").json()["count"] == 1
    assert c.get(f"{BASE}/inviti?zona=Altra").json()["count"] == 0
    assert c.get(f"{BASE}/inviti?gruppo=Gruppo API").json()["count"] == 1
    assert c.get(f"{BASE}/inviti?q=csq").json()["count"] == 1
    assert c.get(f"{BASE}/inviti?q=nessuno").json()["count"] == 0


def test_crp_condiviso_eredita_invito(client_di, edizione, org, utenti, invito_crp):
    """Un Capo Reparto con due squadriglie: l'invito vale per entrambe le righe."""
    from apps.diaries.models import Diario, StatoDiario, TipoDiario

    Diario.objects.create(
        edizione=edizione, squadriglia=org["squadriglia_altra"], crp=utenti["crp"].socio,
        tipo=TipoDiario.NUOVO, stato=StatoDiario.NON_INIZIATO,
    )
    righe = client_di("admin").get(f"{BASE}/inviti").json()["items"]
    assert len(righe) == 2
    assert all(r["ultimo_invito_crp"]["id"] == invito_crp.pk for r in righe)
    riepilogo = client_di("admin").get(f"{BASE}/inviti/riepilogo").json()
    assert riepilogo["contatori"]["capi_totale"] == 1
    assert riepilogo["contatori"]["capi_inviati"] == 1
    assert riepilogo["contatori"]["csq_totale"] == 2


@pytest.mark.parametrize("ruolo", ["crp", "pgv", "csq"])
def test_lista_inviti_vietata(client_di, ruolo):
    assert client_di(ruolo).get(f"{BASE}/inviti").status_code == 403
    assert client_di(ruolo).get(f"{BASE}/inviti/riepilogo").status_code == 403


def test_lista_inviti_anonimo(client_di):
    assert client_di("anonimo").get(f"{BASE}/inviti").status_code == 401


def test_riepilogo_senza_edizione(client_di):
    r = client_di("admin").get(f"{BASE}/inviti/riepilogo")
    assert r.status_code == 200
    assert r.json()["edizione"] is None


def test_riepilogo(client_di, invito_csq):
    r = client_di("incaricato_eg").get(f"{BASE}/inviti/riepilogo")
    assert r.status_code == 200
    body = r.json()
    assert body["edizione"]["anno"] == 2098
    assert body["contatori"]["csq_inviati"] == 1
    assert body["zone"] == ["Zona API"]
    assert body["backend_massivo_display"]


@pytest.mark.parametrize(("tipo", "task"), [
    ("capi", "task_invia_inviti_capi_edizione"), ("csq", "task_invia_inviti_csq_edizione"),
])
def test_invia_inviti_edizione(client_di, edizione, niente_celery, tipo, task):
    r = client_di("segreteria").post(
        f"{BASE}/inviti/invia-edizione", **json_body({"tipo": tipo, "backend": "standard"})
    )
    assert r.status_code == 202
    (args, kwargs), = niente_celery[task]
    assert args == (edizione.pk,)
    assert kwargs == {"backend_tipo": "standard"}


def test_invia_inviti_edizione_validazione(client_di, edizione):
    c = client_di("admin")
    assert c.post(f"{BASE}/inviti/invia-edizione",
                  **json_body({"tipo": "altro"})).status_code == 422
    assert c.post(f"{BASE}/inviti/invia-edizione",
                  **json_body({"tipo": "capi", "backend": "smtp"})).status_code == 422


def test_invia_inviti_edizione_senza_edizione(client_di):
    r = client_di("admin").post(f"{BASE}/inviti/invia-edizione", **json_body({"tipo": "capi"}))
    assert r.status_code == 422


def test_invia_inviti_edizione_vietata(client_di, edizione):
    assert client_di("crp").post(
        f"{BASE}/inviti/invia-edizione", **json_body({"tipo": "capi"})
    ).status_code == 403


def test_invia_inviti_diario(client_di, diario, niente_celery):
    r = client_di("admin").post(f"{BASE}/diari/{diario.pk}/inviti", **json_body({"ruoli": ["csq"]}))
    assert r.status_code == 202
    assert niente_celery["task_invia_inviti_bulk"] == [((diario.pk, ["csq"]), {})]
    assert client_di("admin").post(
        f"{BASE}/diari/{diario.pk}/inviti", **json_body({"ruoli": ["pgv"]})
    ).status_code == 422
    assert client_di("admin").post(
        f"{BASE}/diari/999999/inviti", **json_body({})
    ).status_code == 404
    assert client_di("crp").post(
        f"{BASE}/diari/{diario.pk}/inviti", **json_body({})
    ).status_code == 403


# --- Capo Reparto -------------------------------------------------------------

def test_inviti_crp(client_di, invito_csq):
    r = client_di("crp").get(f"{BASE}/inviti/miei")
    assert r.status_code == 200
    body = r.json()
    assert body["edizione"]["anno"] == 2098
    (riga,) = body["righe"]
    assert riga["ultimo_invito_csq"]["id"] == invito_csq.pk
    assert riga["reinviabile"] is True


@pytest.mark.parametrize("ruolo", ["segreteria", "csq", "pgv"])
def test_inviti_crp_solo_capo_reparto(client_di, ruolo):
    assert client_di(ruolo).get(f"{BASE}/inviti/miei").status_code == 403


# --- Reinvio -----------------------------------------------------------------

def test_reinvio_staff(client_di, invito_crp, niente_celery):
    r = client_di("segreteria").post(f"{BASE}/inviti/{invito_crp.pk}/reinvia")
    assert r.status_code == 200
    invito_crp.refresh_from_db()
    assert invito_crp.stato == StatoInvito.SCADUTO
    nuovo = Invito.objects.get(pk=r.json()["invito"]["id"])
    assert nuovo.stato == StatoInvito.INVIATO and nuovo.token != invito_crp.token
    assert len(niente_celery["task_invia_invito"]) == 1


def test_reinvio_crp_mantiene_codice_socio(client_di, invito_csq):
    """Il Capo Reparto reinvia al proprio Capo Squadriglia; il nuovo invito resta CODICE_SOCIO."""
    r = client_di("crp").post(f"{BASE}/inviti/{invito_csq.pk}/reinvia")
    assert r.status_code == 200
    assert r.json()["invito"]["tipo"] == TipoInvito.CODICE_SOCIO


def test_reinvio_crp_altrui_o_ruolo_diverso(client_di, invito_crp, invito_csq, diario, utenti, org):
    from apps.org.models import Socio

    # invito al Capo Reparto: il Capo Reparto non può reinviarlo
    assert client_di("crp").post(f"{BASE}/inviti/{invito_crp.pk}/reinvia").status_code == 403
    # diario di un altro Capo Reparto
    altro = Socio.objects.create(codice_socio="700099", nome="Altro", cognome="Crp",
                                 categoria="capo", zona=org["zona"], gruppo=org["gruppo"])
    diario.crp = altro
    diario.save(update_fields=["crp"])
    assert client_di("crp").post(f"{BASE}/inviti/{invito_csq.pk}/reinvia").status_code == 403
    for ruolo in ("pgv", "csq"):
        assert client_di(ruolo).post(f"{BASE}/inviti/{invito_csq.pk}/reinvia").status_code == 403
    assert client_di("anonimo").post(f"{BASE}/inviti/{invito_csq.pk}/reinvia").status_code == 401


def test_reinvio_invito_attivato(client_di, invito_crp):
    invito_crp.attiva()
    assert client_di("admin").post(f"{BASE}/inviti/{invito_crp.pk}/reinvia").status_code == 422
    assert client_di("admin").post(f"{BASE}/inviti/999999/reinvia").status_code == 404


# --- Attivazione (pubblica) ----------------------------------------------------

def _nuovo_csq(org, diario, email="noemail.88888@noemail.internal"):
    from apps.org.models import Socio

    socio = Socio.objects.create(codice_socio="88888", nome="Nuovo", cognome="Csq",
                                 categoria="ragazzo", zona=org["zona"], gruppo=org["gruppo"])
    utente = User.objects.create_user(username="88888", email=email, ruolo=Ruolo.CSQ, socio=socio)
    return Invito.objects.create(diario=diario, utente=utente, ruolo_target=Ruolo.CSQ,
                                 tipo=TipoInvito.CODICE_SOCIO)


def test_invito_pubblico(client_di, invito_csq):
    r = client_di("anonimo").get(f"{BASE}/inviti/{invito_csq.token}")
    assert r.status_code == 200
    body = r.json()
    assert body["attivabile"] is True
    assert body["richiede_codice_socio"] is True
    assert body["squadriglia"] == "Tigri"
    assert "email" not in body


def test_invito_pubblico_scaduto_e_inesistente(client_di, invito_csq):
    import uuid

    invito_csq.stato = StatoInvito.SCADUTO
    invito_csq.save()
    body = client_di("anonimo").get(f"{BASE}/inviti/{invito_csq.token}").json()
    assert body["attivabile"] is False and "scaduto" in body["messaggio"]
    assert client_di("anonimo").get(f"{BASE}/inviti/{uuid.uuid4()}").status_code == 404


def test_attiva_csq_con_codice_socio(org, diario):
    invito = _nuovo_csq(org, diario)
    c = Client()
    r = c.post(f"{BASE}/inviti/{invito.token}/attiva",
               **json_body({"codice_socio": "88888", "email": "Nuovo.Csq@Example.it"}))
    assert r.status_code == 200, r.content
    assert r.json()["diario_id"] == diario.pk
    invito.refresh_from_db()
    assert invito.stato == StatoInvito.ATTIVATO
    utente = invito.utente
    utente.refresh_from_db()
    assert utente.email == "nuovo.csq@example.it"
    assert utente.socio.email == "nuovo.csq@example.it"
    assert Nomina.objects.filter(utente=utente, ruolo=Ruolo.CSQ, attiva=True).exists()
    # login avvenuto nella sessione
    assert c.get("/api/v1/me").status_code == 200
    # secondo uso dello stesso token
    r2 = Client().post(f"{BASE}/inviti/{invito.token}/attiva",
                       **json_body({"codice_socio": "88888", "email": "nuovo.csq@example.it"}))
    assert r2.status_code == 422


@pytest.mark.parametrize(("dati", "campo"), [
    ({"codice_socio": "11111", "email": "a@b.it"}, "codice_socio"),
    ({"codice_socio": "88888", "email": ""}, "email"),
    ({"codice_socio": "88888", "email": "non-valida"}, "email"),
    ({"codice_socio": "88888", "email": "crp@test.it"}, "email"),  # già registrata
])
def test_attiva_csq_errori(org, diario, utenti, dati, campo):
    invito = _nuovo_csq(org, diario)
    c = Client()
    r = c.post(f"{BASE}/inviti/{invito.token}/attiva", **json_body(dati))
    assert r.status_code == 422
    assert campo in r.json()["errori"]
    invito.refresh_from_db()
    assert invito.stato == StatoInvito.INVIATO
    assert c.get("/api/v1/me").status_code == 401


def test_attiva_standard(invito_crp, utenti):
    utenti["crp"].set_unusable_password()
    utenti["crp"].save()
    c = Client()
    r = c.post(f"{BASE}/inviti/{invito_crp.token}/attiva", **json_body({}))
    assert r.status_code == 200
    assert r.json()["ruolo"] == Ruolo.CRP and r.json()["login"] is True
    assert c.get("/api/v1/me").json()["email"] == utenti["crp"].email


@pytest.mark.parametrize("caso", ["con_password", "staff"])
def test_attiva_senza_login_per_chi_ha_credenziali(invito_crp, utenti, caso):
    """Il link dell'invito non deve aggirare password e MFA di un account esistente."""
    utente = utenti["crp"]
    if caso == "staff":
        utente.set_unusable_password()
        utente.save()
        Nomina.objects.create(utente=utente, ruolo=Ruolo.SEGRETERIA, attiva=True)
    c = Client()
    r = c.post(f"{BASE}/inviti/{invito_crp.token}/attiva", **json_body({}))
    assert r.status_code == 200
    assert r.json()["login"] is False
    invito_crp.refresh_from_db()
    assert invito_crp.stato == StatoInvito.ATTIVATO
    assert c.get("/api/v1/me").status_code == 401


def test_attiva_scaduto(invito_crp):
    invito_crp.stato = StatoInvito.SCADUTO
    invito_crp.save()
    assert Client().post(f"{BASE}/inviti/{invito_crp.token}/attiva", **json_body({})).status_code == 422


def test_attiva_richiede_csrf(invito_crp):
    c = Client(enforce_csrf_checks=True)
    assert c.post(f"{BASE}/inviti/{invito_crp.token}/attiva", **json_body({})).status_code == 403
    invito_crp.refresh_from_db()
    assert invito_crp.stato == StatoInvito.INVIATO


def test_attiva_crea_nomina_mancante(invito_crp, utenti):
    """Utente con un altro ruolo attivo: riceve la Nomina, il ruolo attivo non cambia."""
    u = utenti["crp"]
    Nomina.objects.filter(utente=u).update(ruolo=Ruolo.PGV)
    r = Client().post(f"{BASE}/inviti/{invito_crp.token}/attiva", **json_body({}))
    assert r.status_code == 200
    assert Nomina.objects.filter(utente=u, ruolo=Ruolo.CRP, attiva=True).exists()


# --- Viste web (regressione dopo l'estrazione nei servizi) ---------------------------

@pytest.fixture
def senza_mfa(monkeypatch):
    monkeypatch.setattr("apps.accounts.middleware.ruolo_richiede_mfa", lambda user: False)


def test_web_attivazione_codice_socio(org, diario, senza_mfa):
    invito = _nuovo_csq(org, diario)
    c = Client()
    url = f"/notifiche/invito/{invito.token}/"
    assert c.get(url).status_code == 200
    r = c.post(url, {"codice_socio": "00000", "email": "x@y.it"})
    assert r.status_code == 200 and "Codice socio non corretto" in r.content.decode()
    r = c.post(url, {"codice_socio": "88888", "email": "web.csq@example.it"})
    assert r.status_code == 302
    invito.refresh_from_db()
    assert invito.stato == StatoInvito.ATTIVATO


def test_web_reinvio_crp(client_di, invito_csq, senza_mfa):
    r = client_di("crp").post(f"/notifiche/invito/{invito_csq.pk}/reinvia/")
    assert r.status_code == 302
    nuovo = Invito.objects.exclude(pk=invito_csq.pk).get()
    assert nuovo.tipo == TipoInvito.CODICE_SOCIO
