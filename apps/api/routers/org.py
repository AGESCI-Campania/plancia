# apps/api/routers/org.py
from django.core.exceptions import PermissionDenied
from ninja import Query, Router

from apps.api.errors import ErroreSchema
from apps.api.schemas.org import (
    GruppoSchema,
    RepartoSchema,
    SocioAutocompleteSchema,
    SquadrigliaSchema,
    ZonaSchema,
)

router = Router(tags=["org"])


@router.get("/albero", response=list[ZonaSchema], summary="Albero organizzativo completo")
def get_albero(request):
    from apps.org.models import Zona

    zone = Zona.objects.prefetch_related(
        "gruppi__reparti__squadriglie"
    ).order_by("nome")

    return [
        ZonaSchema(
            id=z.pk,
            nome=z.nome,
            gruppi=[
                GruppoSchema(
                    id=g.pk,
                    nome=g.nome,
                    reparti=[
                        RepartoSchema(
                            id=r.pk,
                            nome=r.nome,
                            squadriglie=[
                                SquadrigliaSchema(id=s.pk, nome=s.nome)
                                for s in r.squadriglie.all()
                            ],
                        )
                        for r in g.reparti.all()
                    ],
                )
                for g in z.gruppi.all()
            ],
        )
        for z in zone
    ]


@router.get(
    "/soci",
    response={200: list[SocioAutocompleteSchema], 401: ErroreSchema, 403: ErroreSchema},
    summary="Autocompletamento Socio",
)
def cerca_soci(
    request,
    q: str | None = Query(None),
    categoria: str | None = Query(None),
    ruolo: str | None = Query(None),
):
    """Massimo 20 Soci (stessi filtri di `GET /api/soci/`).

    Riservato a chi oggi usa l'autocompletamento: Admin, Segreteria e Incaricati EG
    (utenti, assegnazione Pattuglia GV, import, cambio referenti) e il Capo Reparto
    (cambio Capo Squadriglia), che vede solo i ragazzi (`categoria` forzata a `ragazzo`).
    """
    from apps.accounts.models import Ruolo
    from apps.api.permissions import is_staff_plancia
    from apps.org.services import cerca_soci as _cerca
    from apps.org.services import etichetta, utente_pk

    user = request.auth
    if not is_staff_plancia(user):
        if user.ruolo != Ruolo.CRP:
            raise PermissionDenied("Il tuo ruolo non consente la ricerca dei soci.")
        categoria = "ragazzo"
    return [
        SocioAutocompleteSchema(
            id=s.pk, user_pk=utente_pk(s), codice_socio=s.codice_socio, categoria=s.categoria,
            nome=s.nome, cognome=s.cognome, gruppo=s.gruppo.nome, zona=s.zona.nome,
            label=etichetta(s),
        )
        for s in _cerca(q, categoria, ruolo)
    ]
