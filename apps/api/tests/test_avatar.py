"""Endpoint dell'immagine del profilo (`/me/avatar`, `/utenti/{id}/avatar`)."""
import pytest

from apps.accounts.avatar import allinea_avatar
from apps.accounts.tests.test_avatar import _da_userinfo, _data_uri, _immagine, _utente

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


class TestApiAvatar:
    def test_me_e_scheda_utente(self, client):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        u.refresh_from_db()
        client.force_login(u)
        me = client.get("/api/v1/me").json()
        assert me["avatar_url"] == f"/api/v1/me/avatar?v={u.avatar_sha256[:12]}"
        r = client.get("/api/v1/me/avatar")
        assert r.status_code == 200 and r["Content-Type"] == "image/png"
        assert b"".join(r.streaming_content) == _immagine()

    def test_scheda_utente_per_lo_staff(self, client_di):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        admin = client_di("admin")
        assert admin.get(f"/api/v1/utenti/{u.pk}").json()["avatar_url"].startswith(f"/api/v1/utenti/{u.pk}/avatar?v=")
        assert admin.get(f"/api/v1/utenti/{u.pk}/avatar").status_code == 200

    def test_senza_foto_404(self, client):
        u = _utente()
        client.force_login(u)
        assert client.get("/api/v1/me").json()["avatar_url"] is None
        assert client.get("/api/v1/me/avatar").status_code == 404

    def test_non_staff_non_vede_la_foto_altrui(self, client_di):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        assert client_di("crp").get(f"/api/v1/utenti/{u.pk}/avatar").status_code == 403

    def test_file_cancellato_con_l_utente(self, tmp_path):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        file = tmp_path / u.avatar.name
        u.delete()
        assert not file.exists()
