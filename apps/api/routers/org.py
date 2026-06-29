# apps/api/routers/org.py
from ninja import Router

from apps.api.schemas.org import GruppoSchema, RepartoSchema, SquadrigliaSchema, ZonaSchema

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
