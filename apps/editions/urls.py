# apps/editions/urls.py
from django.urls import path

from apps.editions.views import (
    DilazioneCreateView,
    EdizioneCambioStatoView,
    EdizioneCreateView,
    EdizioneDetailView,
    EdizioneListView,
    EdizioneUpdateView,
    EsitiExcelView,
    EsitiExcelViewerView,
    ExportDiariView,
)

app_name = "editions"

urlpatterns = [
    path("", EdizioneListView.as_view(), name="list"),
    path("nuova/", EdizioneCreateView.as_view(), name="create"),
    path("<int:pk>/", EdizioneDetailView.as_view(), name="detail"),
    path("<int:pk>/modifica/", EdizioneUpdateView.as_view(), name="update"),
    path("<int:pk>/stato/<str:azione>/", EdizioneCambioStatoView.as_view(), name="stato"),
    path("dilazione/<int:pk>/", DilazioneCreateView.as_view(), name="dilazione"),
    path("<int:pk>/excel/", EsitiExcelView.as_view(), name="excel"),
    path("<int:pk>/excel/visualizza/", EsitiExcelViewerView.as_view(), name="excel_viewer"),
    path("<int:pk>/export-diari/", ExportDiariView.as_view(), name="export_diari"),
]
