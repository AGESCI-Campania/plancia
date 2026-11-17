"""Gestione utenti: lista, dettaglio, creazione (staff / da Socio), nomine, impersonazione.

Accesso: Admin, Segreteria e Incaricati EG (come `StaffPlanciaRequiredMixin`); le regole fini
(chi nomina cosa, categoria, esclusività Capo Squadriglia, ranghi d'impersonazione) stanno in
`apps.accounts.roles` e `apps.accounts.services`.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from ninja import Query, Router, Status
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination, paginate

from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.permissions import richiedi_staff
from apps.api.routers.me import (
    login_event_schema,
    me_schema,
    nomina_schema,
    nomine_di,
    risposta_avatar,
    ruolo_schema,
    socio_schema,
    url_avatar,
)
from apps.api.schemas.me import MeEstesoSchema, NominaSchema, RuoloSchema
from apps.api.schemas.utenti import (
    NominaCreaSchema,
    OpzioniUtentiSchema,
    UtenteCreatoSchema,
    UtenteDaSocioCreaSchema,
    UtenteDettaglioSchema,
    UtenteListaSchema,
    UtenteNomePatchSchema,
    UtenteStaffCreaSchema,
)

router = Router(tags=["utenti"])

_ERRORI = {401: ErroreSchema, 403: ErroreSchema, 404: ErroreSchema,
           422: ErroreValidazioneSchema}


@contextmanager
def _errori_nomina() -> Iterator[None]:
    """`roles.nomina` solleva PermissionError/ValueError: li traduce in 403/422."""
    try:
        yield
    except PermissionError as exc:
        raise PermissionDenied(str(exc)) from None
    except ValueError as exc:
        raise ValidationError({"__all__": str(exc)}) from None


def _ruoli(coppie: list[tuple[str, str]]) -> list[RuoloSchema]:
    return [RuoloSchema(chiave=k, etichetta=str(v)) for k, v in coppie]


def _dettaglio(attore, u) -> UtenteDettaglioSchema:
    from apps.accounts import services
    from apps.accounts.roles import puo_impersonare, puo_modificare_nome_di

    return UtenteDettaglioSchema(
        id=u.pk, email=u.email, nome_completo=u.nome_completo,
        first_name=u.first_name, last_name=u.last_name,
        ruolo=ruolo_schema(u.ruolo),
        ruoli_attivi=[ruolo_schema(r) for r in u.ruoli_attivi],
        is_active=u.is_active, is_staff=u.is_staff, is_superuser=u.is_superuser,
        socio=socio_schema(u.socio),
        nomine=nomine_di(u),
        accessi=[login_event_schema(e) for e in u.login_events.all()[:20]],
        ruoli_nominabili=_ruoli(services.ruoli_nominabili(attore)),
        puo_impersonare=puo_impersonare(attore, u),
        puo_modificare_nome=puo_modificare_nome_di(attore, u),
        avatar_url=url_avatar(u, f"/utenti/{u.pk}/avatar"),
    )


def _get_utente(utente_id: int):
    from apps.accounts.models import User

    return get_object_or_404(User.objects.select_related("socio__gruppo", "socio__zona"),
                             pk=utente_id)


@router.get("", response=list[UtenteListaSchema], summary="Lista utenti")
@paginate(LimitOffsetPagination)
def lista_utenti(request, q: str | None = Query(None), ruolo: str | None = Query(None)):
    """Filtri come la pagina Utenti: `ruolo` (attivo) e `q` (email, nome o cognome del socio)."""
    from apps.accounts import services

    richiedi_staff(request.auth)
    return [
        UtenteListaSchema(
            id=u.pk, email=u.email, nome_completo=u.nome_completo,
            ruolo=ruolo_schema(u.ruolo), is_active=u.is_active, socio=socio_schema(u.socio),
        )
        for u in services.utenti_filtrati(ruolo, q)
    ]


@router.get("/opzioni", response={200: OpzioniUtentiSchema, **_ERRORI},
            summary="Ruoli disponibili nei form della gestione utenti")
def opzioni(request):
    from apps.accounts import services
    from apps.accounts.models import Ruolo
    from apps.accounts.roles import IMPERSONATORI

    attore = request.auth
    richiedi_staff(attore)
    return OpzioniUtentiSchema(
        ruoli=_ruoli(Ruolo.choices),
        ruoli_nominabili=_ruoli(services.ruoli_nominabili(attore)),
        ruoli_nominabili_da_socio=_ruoli(services.ruoli_nominabili(attore, solo_capi=True)),
        ruoli_staff_creabili=_ruoli(services.ruoli_staff_creabili(attore)),
        puo_impersonare=attore.ruolo in IMPERSONATORI,
    )


@router.post("/staff", response={201: UtenteCreatoSchema, **_ERRORI},
             summary="Crea un utente staff senza Socio")
def crea_staff(request, payload: UtenteStaffCreaSchema):
    """Admin/Segreteria/Incaricato EG senza Socio; invia l'email per impostare la password."""
    from apps.accounts import services
    from apps.accounts.models import Ruolo

    attore = request.auth
    richiedi_staff(attore)
    with _errori_nomina():
        utente, n, creato, email_inviata = services.crea_utente_staff(
            attore, payload.email, payload.first_name, payload.last_name, payload.ruolo,
            request=request,
        )
    azione = "creato" if creato else "già esistente — nomina aggiunta"
    esito_email = (
        "È stata inviata un'email per impostare la password."
        if email_inviata
        else "Non è stato possibile inviare l'email per impostare la password: controlla la "
             "configurazione della posta e usa «Password dimenticata» dalla pagina di accesso."
    )
    return Status(201, UtenteCreatoSchema(
        utente=_dettaglio(attore, utente), nomina=nomina_schema(n), creato=creato,
        detail=f"Utente {utente.email} {azione} con ruolo {Ruolo(payload.ruolo).label}. "
               f"{esito_email}",
    ))


@router.post("/da-socio", response={201: UtenteCreatoSchema, **_ERRORI},
             summary="Crea l'account di un Socio capo e lo nomina")
def crea_da_socio(request, payload: UtenteDaSocioCreaSchema):
    from apps.accounts import services
    from apps.accounts.models import Ruolo, User

    attore = request.auth
    richiedi_staff(attore)
    esisteva = User.objects.filter(socio_id=payload.socio_id).exists()
    with _errori_nomina():
        utente, n = services.crea_utente_da_socio(attore, payload.socio_id, payload.ruolo)
    return Status(201, UtenteCreatoSchema(
        utente=_dettaglio(attore, utente), nomina=nomina_schema(n), creato=not esisteva,
        detail=f"Account creato e ruolo {Ruolo(payload.ruolo).label} assegnato a {utente.socio}.",
    ))


@router.get("/{utente_id}", response={200: UtenteDettaglioSchema, **_ERRORI},
            summary="Dettaglio utente con storico nomine e accessi")
def dettaglio(request, utente_id: int):
    richiedi_staff(request.auth)
    return _dettaglio(request.auth, _get_utente(utente_id))


@router.get("/{utente_id}/avatar", response={200: None, **_ERRORI},
            summary="Immagine del profilo di un utente (staff)")
def avatar_utente(request, utente_id: int):
    richiedi_staff(request.auth)
    return risposta_avatar(_get_utente(utente_id))


@router.patch("/{utente_id}", response={200: UtenteDettaglioSchema, **_ERRORI},
              summary="Modifica nome e cognome (Admin, Segreteria; utenti senza Socio)")
def modifica_nome(request, utente_id: int, payload: UtenteNomePatchSchema):
    from apps.accounts import services

    richiedi_staff(request.auth)
    utente = _get_utente(utente_id)
    services.aggiorna_nome(utente, payload.first_name, payload.last_name, attore=request.auth)
    return _dettaglio(request.auth, utente)


@router.post("/{utente_id}/nomine", response={201: NominaSchema, **_ERRORI},
             summary="Assegna un ruolo all'utente")
def crea_nomina(request, utente_id: int, payload: NominaCreaSchema):
    """`roles.nomina`: chi può nominare, categoria del Socio, esclusività Capo Squadriglia."""
    from apps.accounts.models import Ruolo
    from apps.accounts.roles import nomina
    from apps.editions.models import Edizione

    richiedi_staff(request.auth)
    utente = _get_utente(utente_id)
    if payload.ruolo not in Ruolo.values:
        raise ValidationError({"ruolo": "Ruolo non valido."})
    edizione = None
    if payload.edizione_id is not None:
        edizione = Edizione.objects.filter(pk=payload.edizione_id).first()
        if edizione is None:
            raise ValidationError({"edizione_id": "Edizione non trovata."})
    with _errori_nomina():
        n = nomina(request.auth, utente, payload.ruolo, edizione=edizione,
                   scadenza=payload.scadenza)
    return Status(201, nomina_schema(n))


@router.post("/{utente_id}/nomine/{nomina_id}/revoca", response={200: NominaSchema, **_ERRORI},
             summary="Revoca una nomina (resta nello storico)")
def revoca_nomina(request, utente_id: int, nomina_id: int):
    from apps.accounts import services
    from apps.accounts.models import Nomina

    richiedi_staff(request.auth)
    n = get_object_or_404(Nomina.objects.select_related("utente", "nominato_da", "edizione"),
                          pk=nomina_id, utente_id=utente_id)
    return nomina_schema(services.revoca_nomina(request.auth, n))


@router.post("/{utente_id}/impersona", response={200: MeEstesoSchema, **_ERRORI},
             summary="Impersona l'utente")
def impersona(request, utente_id: int):
    """Come `hijack:acquire` (regole `roles.can_hijack`: Admin o Segreteria, rango massimo
    del target non superiore; la Segreteria non impersona chi ha una nomina Admin).

    Solo con cookie di sessione (SPA): il login ruota chiave di sessione e token CSRF.
    Restituisce il profilo dell'utente impersonato.
    """
    from apps.accounts import services
    from apps.accounts.roles import IMPERSONATORI

    if request.auth.ruolo not in IMPERSONATORI:
        raise PermissionDenied("Il tuo ruolo non consente di impersonare altri utenti.")
    if "HTTP_X_SESSION_TOKEN" in request.META:
        raise HttpError(422, "L'impersonazione è disponibile solo dal browser.")
    target = _get_utente(utente_id)
    services.avvia_impersonazione(request, target)
    return me_schema(request, target)
