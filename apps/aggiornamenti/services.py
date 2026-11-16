"""Aggiornamento del server dal web (solo Admin): release GitHub, richieste, stato.

Django scrive SOLO `richiesta.json` nella cartella `settings.AGGIORNAMENTI_DIR`; il runner
sull'host (unit `plancia-aggiorna.path`, Fase 6) la sposta in `in-corso.json`, lancia
`scripts/aggiorna.sh` e scrive l'avanzamento in `stato.json`. Contratto dei file in
`docs/api/fase2-aggiornamenti.md`.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.aggiornamenti.models import (
    STATI_APERTI,
    ReleaseGitHub,
    RichiestaAggiornamento,
    StatoRichiesta,
)
from apps.siteconfig.versione import versione_installata

if TYPE_CHECKING:
    from django.http import HttpRequest

    from apps.accounts.models import User

logger = logging.getLogger(__name__)

URL_ULTIMA_RELEASE = "https://api.github.com/repos/AGESCI-Campania/plancia/releases/latest"
TIMEOUT_GITHUB = 10  # secondi
FILE_RICHIESTA = "richiesta.json"
FILE_IN_CORSO = "in-corso.json"
FILE_STATO = "stato.json"
MAX_RIGHE_LOG = 200
_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
ESITI_FINALI = {
    "completato": StatoRichiesta.COMPLETATO,
    "fallito": StatoRichiesta.FALLITO,
    "annullato": StatoRichiesta.ANNULLATO,
}


class RichiestaInCorso(Exception):
    """C'è già una richiesta di aggiornamento aperta (→ 409)."""


class CartellaNonScrivibile(Exception):
    """`AGGIORNAMENTI_DIR` manca o non è scrivibile (→ 503)."""


# ── Versioni ────────────────────────────────────────────────────────────────


def tag_valido(tag: str) -> bool:
    return bool(_TAG_RE.match(tag or ""))


def versione_tuple(versione: str) -> tuple[int, int, int] | None:
    """`v2.5.0` o `2.5.0` → (2, 5, 0); None se non è nel formato X.Y.Z."""
    v = versione or ""
    m = _TAG_RE.match(v if v.startswith("v") else f"v{v}")
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def e_successiva(tag: str, installata: str) -> bool:
    nuova, attuale = versione_tuple(tag), versione_tuple(installata)
    return bool(nuova and (attuale is None or nuova > attuale))


def aggiornamento_disponibile(release: ReleaseGitHub | None = None) -> bool:
    release = release or ReleaseGitHub.get()
    return tag_valido(release.versione) and e_successiva(release.versione, versione_installata())


# ── Release GitHub ──────────────────────────────────────────────────────────


def controlla_ultima_release() -> ReleaseGitHub:
    """Interroga la GitHub Releases API e salva l'ultima release. Non solleva mai eccezioni:
    gli errori sono loggati e salvati in `ReleaseGitHub.errore`."""
    import requests

    release = ReleaseGitHub.get()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"plancia/{versione_installata()}",
    }
    token = getattr(settings, "GITHUB_TOKEN_RELEASES", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(URL_ULTIMA_RELEASE, headers=headers, timeout=TIMEOUT_GITHUB)
        if r.status_code != 200:
            raise RuntimeError(f"GitHub ha risposto {r.status_code}")
        dati = r.json()
        release.versione = str(dati.get("tag_name") or "")[:40]
        release.nome = str(dati.get("name") or "")[:200]
        release.note = str(dati.get("body") or "")
        release.pubblicata_at = parse_datetime(dati.get("published_at") or "")
        release.url = str(dati.get("html_url") or "")[:500]
        release.errore = ""
    except Exception as exc:
        logger.warning("Controllo dell'ultima release GitHub fallito: %s", exc)
        release.errore = str(exc)[:500] or exc.__class__.__name__
    release.controllata_at = timezone.now()
    release.save()
    return release


# ── File di scambio con l'host ──────────────────────────────────────────────


def cartella() -> Path:
    return Path(settings.AGGIORNAMENTI_DIR)


def scrivi_json_atomico(path: Path, dati: dict[str, Any]) -> None:
    """Scrive `dati` in `path` tramite file temporaneo nella stessa cartella + rename atomico."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dati, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o640)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def leggi_json(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            dati = json.load(f)
    except (OSError, ValueError):
        return None
    return dati if isinstance(dati, dict) else None


# ── Riautenticazione ────────────────────────────────────────────────────────


def autenticazione_recente(request: HttpRequest, user: User) -> bool:
    """True se nella sessione c'è un'autenticazione (login o riautenticazione allauth:
    password, codice, MFA, SSO) più recente di `ACCOUNT_REAUTHENTICATION_TIMEOUT` (300 s)."""
    from allauth.account import app_settings as account_settings
    from allauth.account.internal.flows.login import get_authentication_records

    records = get_authentication_records(request, user)
    adesso = time.time()
    limite = account_settings.REAUTHENTICATION_TIMEOUT
    return any(
        isinstance(r, dict) and adesso - float(r.get("at") or 0) < limite for r in records
    )


def flussi_riautenticazione(user: User) -> list[dict[str, Any]]:
    """Flussi di riautenticazione allauth disponibili (`reauthenticate`, `mfa_reauthenticate`,
    `reauthenticate_by_code`), come li elenca allauth headless nelle sue risposte 401."""
    from allauth.account.internal.flows.reauthentication import get_reauthentication_flows

    try:
        return [
            {k: (list(v) if isinstance(v, list | tuple) else v) for k, v in f.items()}
            for f in get_reauthentication_flows(user)
        ]
    except Exception:  # API interna di allauth: non deve mai bloccare la risposta
        logger.exception("Impossibile elencare i flussi di riautenticazione")
        return []


# ── Richieste ───────────────────────────────────────────────────────────────


def richiesta_aperta() -> RichiestaAggiornamento | None:
    return RichiestaAggiornamento.objects.filter(stato__in=STATI_APERTI).first()


def crea_richiesta(user: User, versione: str) -> RichiestaAggiornamento:
    """Registra la richiesta e scrive `richiesta.json` per il runner sull'host.

    Consentita solo se `versione` è un tag `vX.Y.Z` successivo all'installata e uguale
    all'ultima release nota, e non ci sono altre richieste aperte.
    """
    versione = (versione or "").strip()
    if not tag_valido(versione):
        raise ValidationError({"versione": ["La versione deve essere un tag nel formato vX.Y.Z."]})
    installata = versione_installata()
    with transaction.atomic():
        # Lock sulla riga della release: serializza richieste concorrenti di due Admin.
        release = ReleaseGitHub.objects.select_for_update().filter(pk=1).first()
        if release is None or release.versione != versione:
            raise ValidationError(
                {"versione": ["La versione richiesta non è l'ultima release disponibile."]}
            )
        if not e_successiva(versione, installata):
            raise ValidationError(
                {"versione": [f"La versione {versione} non è successiva a quella installata "
                              f"({installata})."]}
            )
        if richiesta_aperta() or (cartella() / FILE_IN_CORSO).exists() \
                or (cartella() / FILE_RICHIESTA).exists():
            raise RichiestaInCorso("C'è già un aggiornamento in attesa o in corso.")
        richiesta = RichiestaAggiornamento.objects.create(
            versione=versione, versione_partenza=installata, richiesta_da=user,
            richiesta_da_email=user.email or "", messaggio="In attesa di presa in carico.",
        )
        try:
            cartella().mkdir(parents=True, exist_ok=True)
            scrivi_json_atomico(cartella() / FILE_RICHIESTA, {
                "id": richiesta.pk,
                "versione": versione,
                "richiesta_da": richiesta.richiesta_da_email,
                "richiesta_at": richiesta.richiesta_at.isoformat(),
            })
        except OSError as exc:
            logger.error("Impossibile scrivere la richiesta di aggiornamento: %s", exc)
            # rollback della riga: l'aggiornamento non è stato richiesto davvero
            transaction.set_rollback(True)
            raise CartellaNonScrivibile(
                "La cartella degli aggiornamenti non è scrivibile: contatta l'amministratore "
                "del server."
            ) from exc
    logger.info("Aggiornamento a %s richiesto da %s (#%s)", versione, user.email, richiesta.pk)
    return richiesta


def annulla_richiesta(user: User) -> RichiestaAggiornamento:
    """Annulla la richiesta aperta se il runner non l'ha ancora presa in carico
    (`in-corso.json` assente). Rimuove `richiesta.json`."""
    richiesta = richiesta_aperta()
    if richiesta is None:
        raise ValidationError({"__all__": ["Nessun aggiornamento in attesa da annullare."]})
    if (cartella() / FILE_IN_CORSO).exists():
        raise RichiestaInCorso("L'aggiornamento è già in corso sul server: non si può annullare.")
    with contextlib.suppress(OSError):
        (cartella() / FILE_RICHIESTA).unlink()
    richiesta.stato = StatoRichiesta.ANNULLATO
    richiesta.messaggio = f"Annullato da {user.email}."[:500]
    richiesta.completato_at = timezone.now()
    richiesta.save(update_fields=["stato", "messaggio", "completato_at", "aggiornato_at"])
    return richiesta


def leggi_stato() -> dict[str, Any] | None:
    """Contenuto di `stato.json` (scritto dallo script sull'host), o None."""
    return leggi_json(cartella() / FILE_STATO)


def sincronizza_storico(stato: dict[str, Any] | None = None) -> RichiestaAggiornamento | None:
    """Riporta nello storico l'avanzamento letto da `stato.json`; restituisce la richiesta
    a cui si riferisce lo stato (o quella aperta)."""
    stato = leggi_stato() if stato is None else stato
    richiesta = None
    if stato and stato.get("id") is not None:
        try:
            richiesta = RichiestaAggiornamento.objects.filter(pk=int(stato["id"])).first()
        except (TypeError, ValueError):
            richiesta = None
    if richiesta is None or not richiesta.aperta:
        # stato.json assente o di una richiesta già chiusa (lo storico non si riscrive):
        # per quella aperta basta sapere se il runner l'ha presa in carico.
        aperta = richiesta_aperta()
        if aperta is None:
            return richiesta
        if aperta.stato == StatoRichiesta.IN_ATTESA and (cartella() / FILE_IN_CORSO).exists():
            aperta.stato = StatoRichiesta.IN_CORSO
            aperta.messaggio = "Presa in carico dal server."
            aperta.save(update_fields=["stato", "messaggio", "aggiornato_at"])
        return aperta

    campi = ["aggiornato_at"]
    if isinstance(stato.get("fase"), str):
        richiesta.fase = stato["fase"][:40]
        campi.append("fase")
    if isinstance(stato.get("messaggio"), str):
        richiesta.messaggio = stato["messaggio"][:500]
        campi.append("messaggio")
    perc = stato.get("percentuale")
    if isinstance(perc, int | float) and not isinstance(perc, bool):
        richiesta.percentuale = max(0, min(100, int(perc)))
        campi.append("percentuale")
    if isinstance(stato.get("log"), list):
        righe = [str(r) for r in stato["log"]][-MAX_RIGHE_LOG:]
        richiesta.log = "\n".join(righe)
        campi.append("log")
    esito = stato.get("esito")
    if esito in ESITI_FINALI:
        richiesta.stato = ESITI_FINALI[esito]
        richiesta.completato_at = parse_datetime(str(stato.get("aggiornato_at") or "")) \
            or timezone.now()
        campi += ["stato", "completato_at"]
    elif richiesta.stato == StatoRichiesta.IN_ATTESA:
        richiesta.stato = StatoRichiesta.IN_CORSO
        campi.append("stato")
    richiesta.save(update_fields=list(dict.fromkeys(campi)))
    return richiesta
