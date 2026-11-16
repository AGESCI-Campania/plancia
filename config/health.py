# config/health.py
"""Endpoint di healthcheck per Docker (healthcheck del servizio web, `compose up --wait`)."""
from django.db import connection
from django.http import HttpResponse


def healthz(request):
    """200 se l'app risponde e raggiunge il database. Nessuna autenticazione, nessun dato."""
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")
