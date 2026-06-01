# apps/evaluations/urls.py
from django.urls import path

from apps.evaluations import views

app_name = "evaluations"

urlpatterns = [
    path("diari/<int:diario_pk>/", views.ValutazioneDetailView.as_view(), name="detail"),
    path("diari/<int:diario_pk>/assegna-pgv/", views.AssegnaPGVView.as_view(), name="assegna_pgv"),
    path("diari/<int:diario_pk>/valuta/", views.ValutaDirettamenteView.as_view(), name="valuta"),
    path("diari/<int:diario_pk>/proponi/", views.PropostaValutazioneView.as_view(), name="proponi"),
    path("diari/<int:diario_pk>/conferma/", views.ConfermaPropostaView.as_view(), name="conferma"),
    path("diari/<int:diario_pk>/rigetta/", views.RigettaPropostaView.as_view(), name="rigetta"),
    path("diari/<int:diario_pk>/modifica/", views.ModificaValutazioneView.as_view(), name="modifica"),
    path("diari/<int:diario_pk>/pubblica/", views.PubblicaEsitoView.as_view(), name="pubblica"),
    path("edizioni/<int:edizione_pk>/pubblica-tutti/", views.PubblicaEsitiEdizioneView.as_view(), name="pubblica_tutti"),
]
