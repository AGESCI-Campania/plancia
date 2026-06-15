# apps/editions/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View

from apps.accounts.mixins import StaffPlanciaRequiredMixin
from apps.editions.forms import DilazioneForm, EdizioneForm
from apps.editions.models import Edizione, StatoEdizione

_STATO_COLORE = {
    "non_iniziato": "secondary",
    "in_compilazione": "info",
    "relazione_finale": "warning",
    "inviato": "primary",
    "in_valutazione": "warning",
    "in_revisione": "warning",
    "approvato": "success",
    "non_approvato": "danger",
    "maggiori_info": "secondary",
}


class HomeView(LoginRequiredMixin, TemplateView):
    """Reindirizza all'edizione attiva più recente; se assente mostra pagina informativa."""

    template_name = "home_no_edizione.html"

    def get(self, request, *args, **kwargs):
        edizione = (
            Edizione.objects.filter(stato__in=[StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE])
            .order_by("-anno")
            .first()
        )
        if edizione:
            return redirect("editions:detail", pk=edizione.pk)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_items"] = [{"label": "Home", "url": None}]
        return ctx


class EdizioneListView(LoginRequiredMixin, ListView):
    model = Edizione
    template_name = "editions/list.html"
    context_object_name = "edizioni"

    def get_queryset(self):
        return Edizione.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_items"] = [{"label": "Home", "url": "/"}, {"label": "Edizioni", "url": None}]
        return ctx


class EdizioneDetailView(LoginRequiredMixin, DetailView):
    model = Edizione
    template_name = "editions/detail.html"
    context_object_name = "edizione"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_items"] = [{"label": "Home", "url": None}]
        user = self.request.user
        edizione = self.object
        diari = list(self._diari_visibili(edizione, user))
        ctx["diari"] = diari
        ctx["dilazione_form"] = DilazioneForm()
        ctx["puo_gestire"] = user.is_staff_plancia or user.is_superuser
        if user.is_staff_plancia or user.is_superuser:
            ctx["stats_diari"] = self._stats_diari(edizione)
        # Valori unici per i filtri (solo per chi vede più di un diario)
        ctx["zone"] = sorted({d.squadriglia.reparto.gruppo.zona.nome for d in diari})
        ctx["gruppi"] = sorted({d.squadriglia.reparto.gruppo.nome for d in diari})
        ctx["specialita_list"] = sorted({
            d.anagrafica.specialita
            for d in diari
            if hasattr(d, "anagrafica") and d.anagrafica.specialita
        })
        from apps.diaries.models import StatoDiario, TipoDiario
        ctx["stati_diari_choices"] = StatoDiario.choices
        ctx["tipi_diari_choices"] = TipoDiario.choices
        return ctx

    def _stats_diari(self, edizione):
        from apps.diaries.models import StatoDiario
        counts = dict(edizione.diari.values_list("stato").annotate(n=Count("pk")))
        totale = sum(counts.values())
        per_stato = [
            {
                "stato": stato,
                "label": label,
                "totale": counts.get(stato, 0),
                "colore": _STATO_COLORE.get(stato, "secondary"),
                "percentuale": round(counts.get(stato, 0) / totale * 100) if totale else 0,
            }
            for stato, label in StatoDiario.choices
        ]
        return {"per_stato": per_stato, "totale": totale}

    def _diari_visibili(self, edizione, user):
        qs = edizione.diari.select_related(
            "squadriglia__reparto__gruppo__zona",
            "csq", "crp", "anagrafica",
        )
        if user.is_staff_plancia or user.is_superuser:
            return qs
        if user.ruolo == "pgv":
            return qs
        # CSQ: solo il proprio diario
        if user.ruolo == "csq" and user.socio:
            return qs.filter(csq=user.socio)
        # CRP: solo i diari del proprio reparto
        if user.ruolo == "crp" and user.socio:
            return qs.filter(crp=user.socio)
        return qs.none()


class EdizioneCreateView(StaffPlanciaRequiredMixin, CreateView):
    model = Edizione
    form_class = EdizioneForm
    template_name = "editions/form.html"
    success_url = reverse_lazy("editions:list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titolo"] = "Nuova edizione"
        return ctx


class EdizioneUpdateView(StaffPlanciaRequiredMixin, UpdateView):
    model = Edizione
    form_class = EdizioneForm
    template_name = "editions/form.html"

    def get_success_url(self):
        return reverse_lazy("editions:detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titolo"] = f"Modifica {self.object}"
        return ctx


class EdizioneCambioStatoView(StaffPlanciaRequiredMixin, View):
    """Esegue una transizione di stato sull'edizione (apri/avvia_valutazione/chiudi)."""

    def post(self, request, pk, azione):
        edizione = get_object_or_404(Edizione, pk=pk)
        try:
            if azione == "apri":
                edizione.apri()
            elif azione == "avvia_valutazione":
                edizione.avvia_valutazione()
            elif azione == "chiudi":
                edizione.chiudi()
            else:
                raise ValueError(f"Azione non riconosciuta: {azione}")
            messages.success(request, f"Edizione {edizione}: stato aggiornato.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("editions:detail", pk=pk)


class DilazioneCreateView(StaffPlanciaRequiredMixin, View):
    """Crea una dilazione per un diario specifico."""

    def post(self, request, pk):
        from apps.diaries.models import Diario
        diario = get_object_or_404(Diario, pk=pk)
        form = DilazioneForm(request.POST)
        if form.is_valid():
            dilazione = form.save(commit=False)
            dilazione.diario = diario
            dilazione.concessa_da = request.user
            dilazione.save()
            messages.success(request, "Dilazione concessa.")
        else:
            messages.error(request, "Dati non validi per la dilazione.")
        return redirect("editions:detail", pk=diario.edizione_id)
