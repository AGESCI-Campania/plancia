# apps/editions/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View

from apps.accounts.mixins import StaffPlanciaRequiredMixin
from apps.editions.forms import DilazioneForm, EdizioneForm
from apps.editions.models import Dilazione, Edizione, StatoEdizione


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


class EdizioneListView(LoginRequiredMixin, ListView):
    model = Edizione
    template_name = "editions/list.html"
    context_object_name = "edizioni"

    def get_queryset(self):
        return Edizione.objects.all()


class EdizioneDetailView(LoginRequiredMixin, DetailView):
    model = Edizione
    template_name = "editions/detail.html"
    context_object_name = "edizione"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        edizione = self.object
        ctx["diari"] = self._diari_visibili(edizione, user)
        ctx["dilazione_form"] = DilazioneForm()
        ctx["puo_gestire"] = user.is_staff_plancia or user.is_superuser
        return ctx

    def _diari_visibili(self, edizione, user):
        qs = edizione.diari.select_related("squadriglia", "csq", "crp")
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
