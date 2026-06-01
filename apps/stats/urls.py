# apps/stats/urls.py
from django.urls import path

from apps.stats import views

app_name = "stats"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
]
