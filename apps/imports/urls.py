# apps/imports/urls.py
from django.urls import path

from apps.imports import views

app_name = "imports"

urlpatterns = [
    path("", views.ImportLogListView.as_view(), name="log_list"),
    path("<int:pk>/", views.ImportLogDetailView.as_view(), name="log_detail"),
    path("<int:pk>/scarti.csv", views.ScartiCsvView.as_view(), name="scarti_csv"),
    path("<int:pk>/scarti/visualizza/", views.ScartiCsvViewerView.as_view(), name="scarti_viewer"),
    path("riconcilia/<int:riga_pk>/", views.RiconciliaRigaView.as_view(), name="riconcilia"),
    path("<int:log_pk>/riprova/", views.RiprovaAnomalieView.as_view(), name="riprova_anomalie"),
]
