"""Login headless (SPA) con email o codice socio, come nella 2.x."""
import json

import pytest
from django.test import Client

from apps.accounts.models import Ruolo, User

pytestmark = pytest.mark.django_db
URL = "/_allauth/browser/v1/auth/login"


@pytest.fixture
def csq(db):
    from allauth.account.models import EmailAddress

    u = User.objects.create_user(
        username="123456", email="noemail.123456@noemail.internal", password="Pw-prova-2026!",
        ruolo=Ruolo.CSQ,
    )
    EmailAddress.objects.create(user=u, email=u.email, verified=True, primary=True)
    return u


@pytest.mark.parametrize("corpo", [
    {"username": "123456", "password": "Pw-prova-2026!"},
    {"email": "noemail.123456@noemail.internal", "password": "Pw-prova-2026!"},
])
def test_login_con_codice_socio_o_email(csq, corpo):
    r = Client().post(URL, data=json.dumps(corpo), content_type="application/json")
    assert r.status_code == 200, r.content
    assert r.json()["data"]["user"]["id"] == csq.pk


def test_password_sbagliata(csq):
    r = Client().post(URL, data=json.dumps({"username": "123456", "password": "no"}),
                      content_type="application/json")
    assert r.status_code == 400
