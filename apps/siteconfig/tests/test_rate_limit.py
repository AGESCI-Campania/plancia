"""Chiave del rate limit API: per sessione esistente, altrimenti per IP reale."""
import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, override_settings

from apps.siteconfig.middleware import _chiave_client

pytestmark = pytest.mark.django_db


@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.db")
def test_sessione_esistente_conta_per_sessione():
    s = SessionStore()
    s.create()
    r = RequestFactory().get("/api/v1/me", REMOTE_ADDR="10.0.0.1")
    r.COOKIES["sessionid"] = s.session_key
    assert _chiave_client(r).startswith("ses:")


def test_cookie_inventato_conta_per_ip_reale():
    r = RequestFactory().get(
        "/api/v1/me", REMOTE_ADDR="10.0.0.1",
        HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7, 10.0.0.2",  # falso, client reale, Caddy
    )
    r.COOKIES["sessionid"] = "inventato"
    assert _chiave_client(r) == "ip:203.0.113.7"
