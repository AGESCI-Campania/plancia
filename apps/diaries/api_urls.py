# apps/diaries/api_urls.py
from django.urls import path

from apps.diaries.api_views import (
    AnagraficaApiView,
    DiarioStatusApiView,
    ImpresaApiView,
    MissioneApiView,
    PresentazioneApiView,
)

urlpatterns = [
    path("<int:pk>/", DiarioStatusApiView.as_view()),
    path("<int:pk>/modulo/anagrafica/", AnagraficaApiView.as_view()),
    path("<int:pk>/modulo/presentazione/", PresentazioneApiView.as_view()),
    path("<int:pk>/modulo/impresa/<int:numero>/", ImpresaApiView.as_view()),
    path("<int:pk>/modulo/missione/", MissioneApiView.as_view()),
]
