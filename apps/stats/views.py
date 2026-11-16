"""Statistiche di chiusura per zona: esiti, tempi, ticket. Vedi docs sez. 13."""
from __future__ import annotations

from django.views.generic import TemplateView

from apps.accounts.mixins import StaffPlanciaRequiredMixin
from apps.stats import services


class DashboardView(StaffPlanciaRequiredMixin, TemplateView):
    """Dashboard statistiche — visibile a Incaricati, Segreteria e Admin.

    Calcoli in `apps.stats.services` (condivisi con l'API).
    """

    template_name = "stats/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.editions.models import Edizione

        edizione = services.edizione_di_riferimento(self.request.GET.get("edizione"))
        ctx["edizioni"] = Edizione.objects.order_by("-anno")
        ctx["edizione"] = edizione
        if edizione:
            ctx["stats_zona"] = services.stats_per_zona(edizione)
            ctx["stats_globali"] = services.stats_globali(edizione)
            ctx["stats_ticket"] = services.stats_ticket(edizione)
        return ctx
