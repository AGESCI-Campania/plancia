"""Test del comportamento dietro il reverse proxy (Caddy → nginx interno)."""
import pytest
from django.test import RequestFactory

from apps.siteconfig.axes_helpers import ip_client_dietro_proxy


class TestIpClientDietroProxy:
    def _req(self, **meta):
        return RequestFactory().get("/accounts/login/", **meta)

    def test_client_e_penultimo_x_forwarded_for(self):
        # Caddy scrive l'IP del client, nginx aggiunge quello di Caddy
        req = self._req(HTTP_X_FORWARDED_FOR="93.40.1.2, 172.18.0.5", REMOTE_ADDR="172.19.0.3")
        assert ip_client_dietro_proxy(req) == "93.40.1.2"

    def test_valore_falsificato_dal_client_ignorato(self):
        req = self._req(
            HTTP_X_FORWARDED_FOR="6.6.6.6, 93.40.1.2, 172.18.0.5", REMOTE_ADDR="172.19.0.3"
        )
        assert ip_client_dietro_proxy(req) == "93.40.1.2"

    def test_senza_intestazione_usa_remote_addr(self):
        req = self._req(REMOTE_ADDR="10.0.0.7")
        assert ip_client_dietro_proxy(req) == "10.0.0.7"


@pytest.mark.django_db
def test_healthz(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.content == b"ok"
