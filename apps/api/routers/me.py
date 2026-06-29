# apps/api/routers/me.py
from ninja import Router

from apps.api.schemas.me import MeSchema, RuoloSchema

router = Router(tags=["me"])


@router.get("/me", response=MeSchema, summary="Profilo utente corrente")
def get_me(request):
    user = request.auth
    return MeSchema(
        id=user.pk,
        email=user.email,
        nome_completo=user.nome_completo,
        ruolo=RuoloSchema(
            chiave=user.ruolo,
            etichetta=user.get_ruolo_display(),
        ),
        ruoli_attivi=[
            RuoloSchema(chiave=chiave, etichetta=etichetta)
            for chiave, etichetta in user.ruoli_attivi_choices
        ],
        is_staff_plancia=user.is_staff_plancia,
        is_superuser=user.is_superuser,
    )
