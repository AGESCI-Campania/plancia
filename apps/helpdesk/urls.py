# apps/helpdesk/urls.py
from django.urls import path

from apps.helpdesk import views

app_name = "helpdesk"

urlpatterns = [
    path("", views.TicketListView.as_view(), name="list"),
    path("nuovo/", views.TicketCreateView.as_view(), name="create"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="detail"),
    path("<int:pk>/rispondi/", views.RispostaTicketView.as_view(), name="rispondi"),
    path("<int:pk>/prendi/", views.TicketPrendiView.as_view(), name="prendi"),
    path("<int:pk>/chiudi/", views.TicketChiudiView.as_view(), name="chiudi"),
]
