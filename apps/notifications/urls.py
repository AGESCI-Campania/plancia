# apps/notifications/urls.py
from django.urls import path

from apps.notifications import views

app_name = "notifications"

urlpatterns = [
    path("inviti/", views.GestioneInvitiView.as_view(), name="gestione_inviti"),
    path("inviti/invia/", views.InviaInvitiEdizoneView.as_view(), name="invia_inviti_edizione"),
    path("inviti/miei/", views.InvitiCrpView.as_view(), name="inviti_crp"),
    path("invito/<uuid:token>/", views.AttivazoneInvitoView.as_view(), name="attiva_invito"),
    path("invito/<int:pk>/reinvia/", views.ReinvioInvitoView.as_view(), name="reinvia_invito"),
    path("diari/<int:diario_pk>/invia-inviti/", views.InvioInvitiBulkView.as_view(), name="invia_inviti_bulk"),
]
