# apps/org/urls.py
from django.urls import path

from apps.org.views import soci_autocomplete

urlpatterns = [
    path("", soci_autocomplete, name="soci_cerca"),
]
