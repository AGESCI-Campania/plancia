from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("profilo/", views.ProfiloView.as_view(), name="profilo"),
    path("utenti/", views.UtenteListView.as_view(), name="utente_list"),
    path("utenti/<int:pk>/", views.UtenteDetailView.as_view(), name="utente_detail"),
    path("utenti/<int:pk>/nomina/", views.NominaView.as_view(), name="nomina"),
    path("cambia-ruolo/", views.CambiaRuoloView.as_view(), name="cambia_ruolo"),
]
