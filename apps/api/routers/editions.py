# apps/api/routers/editions.py
from ninja import Router

from apps.api.schemas.editions import EdizioneSchema

router = Router(tags=["edizioni"])


@router.get("", response=list[EdizioneSchema], summary="Lista edizioni")
def list_edizioni(request):
    from apps.editions.models import Edizione
    return [
        EdizioneSchema(
            id=e.pk,
            anno=e.anno,
            stato=e.stato,
            stato_display=e.get_stato_display(),
            scadenza_evento=e.scadenza_evento,
            scadenza_assemblea=e.scadenza_assemblea,
            data_evento_inizio=e.data_evento_inizio,
            data_evento_fine=e.data_evento_fine,
            evento_comune=e.evento_comune,
        )
        for e in Edizione.objects.all()
    ]


@router.get("/{edizione_id}", response=EdizioneSchema, summary="Dettaglio edizione")
def get_edizione(request, edizione_id: int):
    from django.shortcuts import get_object_or_404

    from apps.editions.models import Edizione
    e = get_object_or_404(Edizione, pk=edizione_id)
    return EdizioneSchema(
        id=e.pk,
        anno=e.anno,
        stato=e.stato,
        stato_display=e.get_stato_display(),
        scadenza_evento=e.scadenza_evento,
        scadenza_assemblea=e.scadenza_assemblea,
        data_evento_inizio=e.data_evento_inizio,
        data_evento_fine=e.data_evento_fine,
        evento_comune=e.evento_comune,
    )
