"""Utente corrente: profilo, ruolo attivo, sessioni, accessi, fine impersonazione.

Le regole stanno in `apps.accounts.services`; qui solo traduzione da/verso JSON.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination, paginate

from apps.api.errors import ErroreSchema, ErroreValidazioneSchema
from apps.api.schemas.me import (
    CambiaRuoloSchema,
    LoginEventSchema,
    MeEstesoSchema,
    MenuSchema,
    NominaSchema,
    ProfiloPatchSchema,
    ProfiloSchema,
    RuoloSchema,
    SessioneSchema,
    SocialAccountSchema,
    SocioBreveSchema,
    TerminaSessioniRispostaSchema,
    UtenteBreveSchema,
)

if TYPE_CHECKING:
    from apps.accounts.models import LoginEvent, Nomina, User
    from apps.org.models import Socio

router = Router(tags=["me"])

_ERRORI = {401: ErroreSchema, 403: ErroreSchema, 422: ErroreValidazioneSchema}


# ---------------------------------------------------------------------------
# Serializzazione (riusata da `routers/utenti.py`)
# ---------------------------------------------------------------------------


def ruolo_schema(chiave: str) -> RuoloSchema:
    from apps.accounts.models import Ruolo

    return RuoloSchema(chiave=chiave, etichetta=Ruolo(chiave).label if chiave in Ruolo.values
                       else chiave)


def utente_breve(u: User | None) -> UtenteBreveSchema | None:
    if u is None:
        return None
    return UtenteBreveSchema(id=u.pk, email=u.email, nome_completo=u.nome_completo)


def socio_schema(s: Socio | None) -> SocioBreveSchema | None:
    if s is None:
        return None
    return SocioBreveSchema(
        id=s.pk, codice_socio=s.codice_socio, nome=s.nome, cognome=s.cognome,
        categoria=s.categoria, categoria_display=s.get_categoria_display(),
        gruppo=s.gruppo.nome if s.gruppo_id else None,
        zona=s.zona.nome if s.zona_id else None,
    )


def nomina_schema(n: Nomina) -> NominaSchema:
    oggi = timezone.now().date()
    return NominaSchema(
        id=n.pk, ruolo=ruolo_schema(n.ruolo), attiva=n.attiva,
        scaduta=bool(n.scadenza and n.scadenza < oggi), scadenza=n.scadenza,
        edizione_id=n.edizione_id, edizione=str(n.edizione) if n.edizione_id else None,
        nominato_da=utente_breve(n.nominato_da), da_sso=n.da_sso, creato_at=n.creato_at,
    )


def login_event_schema(e: LoginEvent) -> LoginEventSchema:
    return LoginEventSchema(
        id=e.pk, creato_at=e.creato_at, esito=e.esito, esito_display=e.get_esito_display(),
        ip=e.ip, provider=e.provider or "email", user_agent=e.user_agent,
    )


def nomine_di(u: User) -> list[NominaSchema]:
    qs = u.nomine.select_related("nominato_da__socio", "edizione").order_by("-creato_at")
    return [nomina_schema(n) for n in qs]


def me_schema(request, user: User) -> MeEstesoSchema:
    from allauth.mfa.utils import is_mfa_enabled

    from apps.accounts import services
    from apps.accounts.adapters import mfa_da_configurare, ruolo_richiede_mfa

    mfa_attiva = is_mfa_enabled(user)
    mfa_richiesta = ruolo_richiede_mfa(user)
    operatore = services.impersonato_da(request)
    return MeEstesoSchema(
        id=user.pk,
        email=user.email,
        nome_completo=user.nome_completo,
        ruolo=RuoloSchema(chiave=user.ruolo, etichetta=user.get_ruolo_display()),
        ruoli_attivi=[
            RuoloSchema(chiave=chiave, etichetta=etichetta)
            for chiave, etichetta in user.ruoli_attivi_choices
        ],
        is_staff_plancia=user.is_staff_plancia,
        is_superuser=user.is_superuser,
        first_name=user.first_name,
        last_name=user.last_name,
        socio=socio_schema(user.socio),
        mfa_attiva=mfa_attiva,
        mfa_richiesta=mfa_richiesta,
        # Stesse esenzioni di MFAEnforcementMiddleware (impersonazione, sessione Sestante)
        mfa_da_configurare=mfa_da_configurare(request, user),
        menu=MenuSchema(**services.flag_menu(user)),
        impersonato_da=utente_breve(operatore),
        puo_modificare_email=services.puo_modificare_email(user),
        puo_modificare_nome=services.puo_modificare_nome(user),
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/me", response={200: MeEstesoSchema, 401: ErroreSchema},
            summary="Profilo utente corrente")
def get_me(request):
    """Dati dell'utente corrente, socio collegato, stato MFA, voci di menu, impersonazione."""
    return me_schema(request, request.auth)


@router.patch("/me", response={200: MeEstesoSchema, **_ERRORI},
              summary="Modifica il proprio profilo")
def patch_me(request, payload: ProfiloPatchSchema):
    """Email (solo Capo Squadriglia, aggiorna anche il Socio); nome e cognome (solo senza Socio)."""
    from django.db import transaction

    from apps.accounts import services

    user = request.auth
    with transaction.atomic():
        if payload.email is not None:
            services.aggiorna_email(user, payload.email)
        if payload.first_name is not None or payload.last_name is not None:
            services.aggiorna_nome(
                user,
                user.first_name if payload.first_name is None else payload.first_name,
                user.last_name if payload.last_name is None else payload.last_name,
            )
    return me_schema(request, user)


@router.get("/me/profilo", response={200: ProfiloSchema, 401: ErroreSchema},
            summary="Pagina profilo: nomine, ultimi accessi, account social")
def get_profilo(request):
    from allauth.socialaccount.models import SocialAccount

    u = request.auth
    social = []
    for sa in SocialAccount.objects.filter(user=u):
        try:
            nome = str(sa.get_provider_account())
        except Exception:  # noqa: BLE001 — provider non più configurato
            nome = sa.provider
        social.append(SocialAccountSchema(
            id=sa.pk, provider=sa.provider, nome_provider=nome, uid=sa.uid,
            email=(sa.extra_data or {}).get("email"),
        ))
    return ProfiloSchema(
        utente=me_schema(request, u),
        nomine=nomine_di(u),
        accessi=[login_event_schema(e) for e in u.login_events.all()[:10]],
        social_accounts=social,
    )


@router.get("/me/nomine", response={200: list[NominaSchema], 401: ErroreSchema},
            summary="Storico delle proprie nomine")
def get_mie_nomine(request):
    return nomine_di(request.auth)


@router.get("/me/accessi", response=list[LoginEventSchema], summary="Propri accessi recenti")
@paginate(LimitOffsetPagination)
def get_miei_accessi(request):
    return [login_event_schema(e) for e in request.auth.login_events.all()]


@router.post("/me/ruolo", response={200: MeEstesoSchema, **_ERRORI},
             summary="Cambia il ruolo attivo")
def cambia_ruolo(request, payload: CambiaRuoloSchema):
    """Il ruolo deve essere tra i ruoli attivi e non scaduti dell'utente (Nomina)."""
    from apps.accounts import services

    services.cambia_ruolo_attivo(request.auth, payload.ruolo)
    return me_schema(request, request.auth)


@router.get("/me/sessioni", response={200: list[SessioneSchema], 401: ErroreSchema},
            summary="Sessioni attive dell'utente")
def get_sessioni(request):
    from allauth.usersessions.models import UserSession

    corrente = request.session.session_key
    return [
        SessioneSchema(
            id=s.pk, ip=s.ip, user_agent=s.user_agent, creato_at=s.created_at,
            ultimo_accesso=s.last_seen_at, corrente=s.session_key == corrente,
        )
        for s in UserSession.objects.purge_and_list(request.auth)
    ]


@router.post("/me/sessioni/termina-altre",
             response={200: TerminaSessioniRispostaSchema, 401: ErroreSchema},
             summary="Termina tutte le altre sessioni")
def termina_altre_sessioni(request):
    from apps.accounts import services

    n = services.termina_altre_sessioni(request.auth, request.session.session_key)
    detail = (f"Terminate {n} sessione/i attiva/e." if n
              else "Nessun'altra sessione attiva da terminare.")
    return TerminaSessioniRispostaSchema(terminate=n, detail=detail)


@router.post("/me/impersonazione/termina", response={200: MeEstesoSchema, **_ERRORI},
             summary="Termina l'impersonazione e torna al proprio utente")
def termina_impersonazione(request):
    """Come `hijack:release`: ripristina l'operatore e invia il segnale `hijack_ended`.

    Il login ruota la chiave di sessione e il token CSRF: la SPA deve rileggere il cookie.
    """
    from apps.accounts import services

    if "HTTP_X_SESSION_TOKEN" in request.META:
        raise HttpError(422, "L'impersonazione è disponibile solo dal browser.")
    operatore = services.termina_impersonazione(request)
    return me_schema(request, operatore)
