# apps/org/views.py
"""Endpoint di autocompletamento per la selezione di capi/ragazzi.

GET /api/soci/?q=<query>&categoria=<capo|ragazzo>[&ruolo=<pgv|crp|...>]
Risponde con { results: [{id, user_pk, codice_socio, label, categoria}, ...] }.
- id       = Socio PK (usato dalla riconciliazione import)
- user_pk  = User PK collegato, o null se l'account non esiste ancora
             (usato dall'assegnazione PGV e ovunque serva un User PK)
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def soci_autocomplete(request):
    from apps.org.services import cerca_soci, etichetta, utente_pk

    qs = cerca_soci(
        request.GET.get("q"), request.GET.get("categoria"), request.GET.get("ruolo")
    )
    results = [
        {
            "id": s.pk,
            "user_pk": utente_pk(s),
            "codice_socio": s.codice_socio,
            "categoria": s.categoria,
            "label": etichetta(s),
        }
        for s in qs
    ]
    return JsonResponse({"results": results})
