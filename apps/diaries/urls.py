# apps/diaries/urls.py
from django.urls import path

from apps.diaries.views import (
    AllegatoDeleteView,
    AllegatoListView,
    AllegatoPreviewView,
    AllegatoUploadView,
    AnagraficaUpdateView,
    CambiaCrpRepartoView,
    CambiaCrpView,
    CambiaCsqView,
    DiarioDetailView,
    DiarioInviaView,
    DiarioListView,
    DiarioRiapriView,
    ImpresaUpdateView,
    MissioneUpdateView,
    PresentazioneUpdateView,
    RelazioneFinaleUpdateView,
)

app_name = "diaries"

urlpatterns = [
    path("", DiarioListView.as_view(), name="list"),
    path("<int:pk>/", DiarioDetailView.as_view(), name="detail"),
    path("<int:pk>/anagrafica/", AnagraficaUpdateView.as_view(), name="anagrafica"),
    path("<int:pk>/presentazione/", PresentazioneUpdateView.as_view(), name="presentazione"),
    path("<int:pk>/impresa/<int:numero>/", ImpresaUpdateView.as_view(), name="impresa"),
    path("<int:pk>/missione/", MissioneUpdateView.as_view(), name="missione"),
    path("<int:pk>/relazione/", RelazioneFinaleUpdateView.as_view(), name="relazione"),
    path("<int:pk>/invia/", DiarioInviaView.as_view(), name="invia"),
    path("<int:pk>/riapri/", DiarioRiapriView.as_view(), name="riapri"),
    path("<int:pk>/cambia-csq/", CambiaCsqView.as_view(), name="cambia_csq"),
    path("<int:pk>/cambia-crp/", CambiaCrpView.as_view(), name="cambia_crp"),
    path(
        "reparto/<int:reparto_pk>/cambia-crp/",
        CambiaCrpRepartoView.as_view(),
        name="cambia_crp_reparto",
    ),
    # Allegati (foto)
    path("<int:pk>/allegati/", AllegatoListView.as_view(), name="allegati_list"),
    path("<int:pk>/allegati/upload/", AllegatoUploadView.as_view(), name="allegati_upload"),
    path(
        "<int:pk>/allegati/<int:allegato_pk>/elimina/",
        AllegatoDeleteView.as_view(),
        name="allegati_delete",
    ),
    path(
        "<int:pk>/allegati/<int:allegato_pk>/preview/",
        AllegatoPreviewView.as_view(),
        name="allegati_preview",
    ),
]
