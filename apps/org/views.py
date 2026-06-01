# apps/org/views.py
"""Endpoint di autocompletamento per la selezione di capi/ragazzi.

GET /api/soci/?q=<query>&categoria=<capo|ragazzo>[&ruolo=<pgv|crp|...>]
Risponde con { results: [{id, user_pk, codice_socio, label, categoria}, ...] }.
- id       = Socio PK (usato dalla riconciliazione import)
- user_pk  = User PK collegato, o null se l'account non esiste ancora
             (usato dall'assegnazione PGV e ovunque serva un User PK)
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse


@login_required
def soci_autocomplete(request):
    from apps.org.models import Socio

    q = (request.GET.get("q") or "").strip()
    categoria = request.GET.get("categoria")  # "capo" | "ragazzo" | None
    ruolo = request.GET.get("ruolo")           # filtra per ruolo utente collegato
    qs = Socio.objects.select_related("gruppo", "zona", "user")
    if categoria:
        qs = qs.filter(categoria=categoria)
    if ruolo:
        qs = qs.filter(user__ruolo=ruolo)
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(cognome__icontains=q)
            | Q(zona__nome__icontains=q)
            | Q(gruppo__nome__icontains=q)
            | Q(codice_socio__startswith=q)
        )
    results = []
    for s in qs[:20]:
        try:
            user_pk = s.user.pk
        except Exception:
            user_pk = None
        results.append({
            "id": s.pk,
            "user_pk": user_pk,
            "codice_socio": s.codice_socio,
            "categoria": s.categoria,
            "label": f"{s.cognome} {s.nome} - {s.gruppo.nome} ({s.zona.nome}) #{s.codice_socio}",
        })
    return JsonResponse({"results": results})
