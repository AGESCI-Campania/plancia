# apps/editions/urls.py
from django.urls import path

from apps.editions.views import (
    DilazioneCreateView,
    EdizioneCambioStatoView,
    EdizioneCreateView,
    EdizioneDetailView,
    EdizioneListView,
    EdizioneUpdateView,
)

app_name = "editions"

urlpatterns = [
    path("", EdizioneListView.as_view(), name="list"),
    path("nuova/", EdizioneCreateView.as_view(), name="create"),
    path("<int:pk>/", EdizioneDetailView.as_view(), name="detail"),
    path("<int:pk>/modifica/", EdizioneUpdateView.as_view(), name="update"),
    path("<int:pk>/stato/<str:azione>/", EdizioneCambioStatoView.as_view(), name="stato"),
    path("dilazione/<int:pk>/", DilazioneCreateView.as_view(), name="dilazione"),
]
