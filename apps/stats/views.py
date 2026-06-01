# apps/stats/views.py
"""Statistiche di chiusura per zona: esiti, tempi, ticket. Vedi docs sez. 13."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q
from django.views.generic import TemplateView

from apps.accounts.mixins import StaffPlanciaRequiredMixin
from apps.accounts.models import Ruolo
from apps.diaries.models import StatoDiario
from apps.evaluations.models import EsitoValutazione
from apps.helpdesk.models import StatoTicket


class DashboardView(StaffPlanciaRequiredMixin, TemplateView):
    """Dashboard statistiche — visibile a Incaricati, Segreteria e Admin."""

    template_name = "stats/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.editions.models import Edizione, StatoEdizione

        edizione_pk = self.request.GET.get("edizione")
        edizioni = Edizione.objects.order_by("-anno")
        edizione = None

        if edizione_pk:
            edizione = edizioni.filter(pk=edizione_pk).first()
        if not edizione:
            edizione = edizioni.filter(
                stato__in=[StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE]
            ).first() or edizioni.first()

        ctx["edizioni"] = edizioni
        ctx["edizione"] = edizione

        if edizione:
            ctx["stats_zona"] = self._stats_per_zona(edizione)
            ctx["stats_globali"] = self._stats_globali(edizione)
            ctx["stats_ticket"] = self._stats_ticket(edizione)

        return ctx

    def _stats_per_zona(self, edizione) -> list[dict]:
        from apps.org.models import Zona
        from apps.diaries.models import Diario

        risultati = []
        for zona in Zona.objects.order_by("nome"):
            diari = Diario.objects.filter(
                edizione=edizione,
                squadriglia__reparto__gruppo__zona=zona,
            )
            totale = diari.count()
            if not totale:
                continue

            approvati = diari.filter(
                valutazione__esito=EsitoValutazione.APPROVATA,
                pubblicato_at__isnull=False,
            ).count()
            non_approvati = diari.filter(
                valutazione__esito=EsitoValutazione.NON_APPROVATA,
                pubblicato_at__isnull=False,
            ).count()
            maggiori_info = diari.filter(
                stato=StatoDiario.MAGGIORI_INFO,
            ).count()
            pubblicati = diari.filter(pubblicato_at__isnull=False).count()

            risultati.append({
                "zona": zona,
                "totale": totale,
                "approvati": approvati,
                "non_approvati": non_approvati,
                "maggiori_info": maggiori_info,
                "pubblicati": pubblicati,
                "percentuale_approvati": round(approvati / totale * 100) if totale else 0,
            })
        return risultati

    def _stats_globali(self, edizione) -> dict:
        from apps.diaries.models import Diario

        diari = Diario.objects.filter(edizione=edizione)
        totale = diari.count()
        return {
            "totale": totale,
            "inviati": diari.filter(
                stato__in=[
                    StatoDiario.INVIATO, StatoDiario.IN_VALUTAZIONE,
                    StatoDiario.IN_REVISIONE, StatoDiario.APPROVATO,
                    StatoDiario.NON_APPROVATO,
                ]
            ).count(),
            "approvati": diari.filter(
                valutazione__esito=EsitoValutazione.APPROVATA, pubblicato_at__isnull=False
            ).count(),
            "non_approvati": diari.filter(
                valutazione__esito=EsitoValutazione.NON_APPROVATA, pubblicato_at__isnull=False
            ).count(),
            "in_compilazione": diari.filter(stato=StatoDiario.IN_COMPILAZIONE).count(),
            "pubblicati": diari.filter(pubblicato_at__isnull=False).count(),
        }

    def _stats_ticket(self, edizione) -> dict:
        from apps.helpdesk.models import CategoriaTicket, Ticket

        tickets = Ticket.objects.filter(diario__edizione=edizione)
        return {
            "totale": tickets.count(),
            "aperti": tickets.filter(stato=StatoTicket.APERTO).count(),
            "chiusi": tickets.filter(stato=StatoTicket.CHIUSO).count(),
            "per_categoria": [
                {
                    "categoria": label,
                    "count": tickets.filter(categoria=val).count(),
                }
                for val, label in CategoriaTicket.choices
            ],
        }
