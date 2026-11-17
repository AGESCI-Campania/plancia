"""Immagine del profilo da Sestante (scope `avatar`, INTEGRAZIONE-SSO.md § 5.1 e § 6 punto 7).

A ogni login SSO la foto locale si allinea al claim `picture` della risposta `userinfo`:
- data-URI (jpeg/png/webp/gif, ≤ 512 KB) → salvata come file, riscritta solo se cambia (hash);
- URL (Gravatar) o assente → nessuna foto da Sestante: si toglie quella arrivata da Sestante.
Gli URL non si scaricano (niente richieste a servizi esterni). Senza `userinfo` (solo
`id_token`) non si tocca niente. Un errore sulla foto non blocca mai il login.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import logging
from dataclasses import dataclass

from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

TIPI_AMMESSI = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
# Formato Pillow atteso per ogni tipo dichiarato nel data-URI
_FORMATI_PILLOW = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP", "image/gif": "GIF"}
DIMENSIONE_MASSIMA = 512 * 1024


@dataclass(frozen=True)
class PictureSestante:
    """Il claim `picture` letto da `extra_data`; `da_userinfo` False = niente risposta userinfo."""

    da_userinfo: bool
    valore: str | None


def estrai_picture(extra_data: dict) -> PictureSestante:
    """Legge `picture` da `userinfo` e ne toglie il data-URI, così allauth non lo salva nel
    database con l'account social (fino a ~700 KB di testo). Gli URL restano."""
    userinfo = extra_data.get("userinfo") if isinstance(extra_data, dict) else None
    if not isinstance(userinfo, dict):
        return PictureSestante(da_userinfo=False, valore=None)
    valore = userinfo.get("picture")
    if isinstance(valore, str) and valore.startswith("data:"):
        userinfo.pop("picture")
    return PictureSestante(da_userinfo=True, valore=valore if isinstance(valore, str) else None)


def _decodifica(data_uri: str) -> tuple[bytes, str]:
    """(contenuto, estensione) del data-URI; ValueError se tipo, dimensione o immagine non vanno."""
    from PIL import Image

    intestazione, _, dati = data_uri.partition(",")
    tipo = intestazione.removeprefix("data:").removesuffix(";base64")
    if not intestazione.endswith(";base64") or tipo not in TIPI_AMMESSI:
        raise ValueError(f"tipo non ammesso: {intestazione[:60]}")
    if len(dati) > DIMENSIONE_MASSIMA * 4 // 3 + 4:
        raise ValueError("immagine troppo grande")
    try:
        contenuto = base64.b64decode(dati, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("base64 non valido") from exc
    if len(contenuto) > DIMENSIONE_MASSIMA:
        raise ValueError("immagine troppo grande")
    try:
        with Image.open(io.BytesIO(contenuto)) as immagine:
            formato = immagine.format
            immagine.verify()
    except Exception as exc:  # noqa: BLE001 - qualunque errore di Pillow = immagine non valida
        raise ValueError("immagine non leggibile") from exc
    if formato != _FORMATI_PILLOW[tipo]:
        raise ValueError(f"il contenuto ({formato}) non è {tipo}")
    return contenuto, TIPI_AMMESSI[tipo]


def _rimuovi(user) -> None:
    if user.avatar:
        user.avatar.delete(save=False)
    user.avatar = ""
    user.avatar_sha256 = ""
    user.avatar_da_sso = False
    user.save(update_fields=["avatar", "avatar_sha256", "avatar_da_sso"])


def allinea_avatar(user, picture: PictureSestante) -> None:
    """Allinea la foto di `user` (già salvato) a quella di Sestante. Non solleva mai."""
    if not picture.da_userinfo or user.pk is None:
        return
    try:
        if picture.valore and picture.valore.startswith("data:"):
            contenuto, estensione = _decodifica(picture.valore)
            impronta = hashlib.sha256(contenuto).hexdigest()
            if user.avatar and user.avatar_sha256 == impronta:
                return
            if user.avatar:
                user.avatar.delete(save=False)
            user.avatar.save(f"sestante.{estensione}", ContentFile(contenuto), save=False)
            user.avatar_sha256 = impronta
            user.avatar_da_sso = True
            user.save(update_fields=["avatar", "avatar_sha256", "avatar_da_sso"])
        elif user.avatar and user.avatar_da_sso:
            # URL (Gravatar) o nessuna foto: su Sestante non c'è più un'immagine caricata
            _rimuovi(user)
    except Exception:  # noqa: BLE001 - la foto non deve mai bloccare il login
        logger.warning("Immagine del profilo da Sestante non allineata per %s", user.pk, exc_info=True)
