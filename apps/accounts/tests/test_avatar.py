"""Immagine del profilo da Sestante (INTEGRAZIONE-SSO.md § 5.1 e § 6 punto 7)."""
import base64
import io

import pytest
from PIL import Image

from apps.accounts.adapters import PlanciaSocialAccountAdapter
from apps.accounts.avatar import PictureSestante, allinea_avatar, estrai_picture
from apps.accounts.models import Ruolo, User
from apps.accounts.tests.test_sso_sestante import _richiesta, _sociallogin

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _immagine(formato: str = "PNG", colore: str = "red") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), colore).save(buffer, format=formato)
    return buffer.getvalue()


def _data_uri(contenuto: bytes, tipo: str = "image/png") -> str:
    return f"data:{tipo};base64,{base64.b64encode(contenuto).decode()}"


def _utente() -> User:
    return User.objects.create_user(username="a@test.it", email="a@test.it", ruolo=Ruolo.SEGRETERIA)


def _da_userinfo(valore: str | None) -> PictureSestante:
    return PictureSestante(da_userinfo=True, valore=valore)


class TestEstraiPicture:
    def test_data_uri_tolto_da_extra_data(self):
        extra = {"userinfo": {"email": "a@test.it", "picture": _data_uri(_immagine())}, "id_token": {}}
        picture = estrai_picture(extra)
        assert picture.da_userinfo and picture.valore.startswith("data:image/png")
        assert "picture" not in extra["userinfo"]

    def test_url_resta(self):
        extra = {"userinfo": {"picture": "https://gravatar.com/avatar/x"}}
        assert estrai_picture(extra).valore == "https://gravatar.com/avatar/x"
        assert extra["userinfo"]["picture"] == "https://gravatar.com/avatar/x"

    def test_senza_userinfo(self):
        assert estrai_picture({"id_token": {"picture": "x"}}).da_userinfo is False


class TestAllineaAvatar:
    def test_salva_e_non_riscrive_se_uguale(self):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        u.refresh_from_db()
        assert u.avatar and u.avatar_da_sso and len(u.avatar_sha256) == 64
        nome = u.avatar.name
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        u.refresh_from_db()
        assert u.avatar.name == nome

    def test_foto_cambiata_sostituisce_il_file(self, tmp_path):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine(colore="red"))))
        vecchio = tmp_path / u.avatar.name
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine(colore="blue"))))
        u.refresh_from_db()
        assert not vecchio.exists()
        assert (tmp_path / u.avatar.name).exists()

    @pytest.mark.parametrize("valore", [None, "https://gravatar.com/avatar/x"])
    def test_assente_o_url_toglie_la_foto_di_sestante(self, valore, tmp_path):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        file = tmp_path / u.avatar.name
        allinea_avatar(u, _da_userinfo(valore))
        u.refresh_from_db()
        assert not u.avatar and not u.avatar_da_sso and not file.exists()

    def test_assente_non_toglie_una_foto_locale(self):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        User.objects.filter(pk=u.pk).update(avatar_da_sso=False)
        u.refresh_from_db()
        allinea_avatar(u, _da_userinfo(None))
        u.refresh_from_db()
        assert u.avatar

    def test_solo_id_token_non_tocca_niente(self):
        u = _utente()
        allinea_avatar(u, _da_userinfo(_data_uri(_immagine())))
        allinea_avatar(u, PictureSestante(da_userinfo=False, valore=None))
        u.refresh_from_db()
        assert u.avatar

    @pytest.mark.parametrize("valore", [
        _data_uri(b"<svg/>", "image/svg+xml"),            # tipo non ammesso
        _data_uri(_immagine("PNG"), "image/jpeg"),        # contenuto diverso dal tipo
        _data_uri(b"non un'immagine"),                    # non leggibile
        "data:image/png;base64,%%%",                      # base64 non valido
        _data_uri(b"0" * (512 * 1024 + 1)),               # troppo grande
    ])
    def test_immagine_non_valida_ignorata_senza_errori(self, valore):
        u = _utente()
        allinea_avatar(u, _da_userinfo(valore))
        u.refresh_from_db()
        assert not u.avatar


class TestLoginSestante:
    @pytest.fixture(autouse=True)
    def _provider_sestante(self, settings):
        settings.SOCIALACCOUNT_PROVIDERS = {"openid_connect": {"SERVERS": [{
            "id": "sestante", "name": "SSO AGESCI Campania",
            "server_url": "https://auth.example.test/application/o/plancia",
            "APP": {"client_id": "id-test", "secret": "secret-test"},
        }]}}

    def test_nuovo_utente_riceve_la_foto(self):
        sl = _sociallogin("nuovo@test.it", [])
        sl.account.extra_data["userinfo"]["picture"] = _data_uri(_immagine())
        sl.account.extra_data["userinfo"]["name"] = "Nuovo Utente"
        adapter = PlanciaSocialAccountAdapter()
        request = _richiesta()
        adapter.pre_social_login(request, sl)
        assert "picture" not in sl.account.extra_data["userinfo"]
        user = adapter.save_user(request, sl)
        user.refresh_from_db()
        assert user.avatar and user.avatar_da_sso

    def test_utente_esistente_collegato_per_email(self):
        u = _utente()
        sl = _sociallogin("a@test.it", [])
        sl.account.extra_data["userinfo"]["picture"] = _data_uri(_immagine())
        PlanciaSocialAccountAdapter().pre_social_login(_richiesta(), sl)
        u.refresh_from_db()
        assert u.avatar
