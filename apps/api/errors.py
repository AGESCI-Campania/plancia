# apps/api/errors.py
"""Errori comuni dell'API: schema della risposta e gestori globali.

I router sollevano le eccezioni di dominio (`apps.evaluations.actions`) o di Django senza
tradurle a mano: i gestori registrati in `api.py` le convertono nel codice HTTP giusto.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from ninja import Schema

if TYPE_CHECKING:
    from ninja import NinjaAPI


class ErroreSchema(Schema):
    """Corpo di ogni risposta di errore (4xx): `detail` leggibile dall'utente."""

    detail: str


class ErroreValidazioneSchema(Schema):
    """Errore di validazione di un form: messaggi per campo (`__all__` = non di campo)."""

    detail: str
    errori: dict[str, list[str]]


def messaggi_validazione(exc: ValidationError) -> dict[str, list[str]]:
    if hasattr(exc, "error_dict"):
        return {campo: [str(m) for e in errori for m in e.messages]
                for campo, errori in exc.error_dict.items()}
    return {"__all__": [str(m) for m in exc.messages]}


def registra_gestori(api: NinjaAPI) -> None:
    from apps.evaluations.actions import AzioneNonConsentita, PermessoNegato

    def _risposta(request, stato: int, corpo: dict[str, Any]):
        return api.create_response(request, corpo, status=stato)

    @api.exception_handler(PermessoNegato)
    def _permesso_negato(request, exc):
        return _risposta(request, 403, {"detail": str(exc) or "Permesso negato."})

    @api.exception_handler(AzioneNonConsentita)
    def _azione_non_consentita(request, exc):
        # StatoNonValido e le altre AzioneNonConsentita (PermessoNegato è sopra)
        return _risposta(request, 422, {"detail": str(exc)})

    @api.exception_handler(PermissionDenied)
    def _permission_denied(request, exc):
        return _risposta(request, 403, {"detail": str(exc) or "Permesso negato."})

    @api.exception_handler(ObjectDoesNotExist)
    def _non_trovato(request, exc):
        return _risposta(request, 404, {"detail": "Non trovato."})

    @api.exception_handler(ValidationError)
    def _validazione(request, exc):
        return _risposta(request, 422, {"detail": "Dati non validi.",
                                        "errori": messaggi_validazione(exc)})
