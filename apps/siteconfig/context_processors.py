from apps.siteconfig.models import Impostazioni


def impostazioni(request):
    return {"impostazioni": Impostazioni.get()}
