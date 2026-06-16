from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("profilo/", views.ProfiloView.as_view(), name="profilo"),
    path("lista/", views.UtenteListView.as_view(), name="utente_list"),
    path("<int:pk>/", views.UtenteDetailView.as_view(), name="utente_detail"),
    path("<int:pk>/nomina/", views.NominaView.as_view(), name="nomina"),
    path("crea-da-socio/", views.CreaUtenteDaSocioView.as_view(), name="crea_da_socio"),
    path("cambia-ruolo/", views.CambiaRuoloView.as_view(), name="cambia_ruolo"),
    path("crea-staff/", views.CreaUtenteStaffView.as_view(), name="crea_staff"),
    path("termina-sessioni/", views.TerminaSessioniView.as_view(), name="termina_sessioni"),
]
