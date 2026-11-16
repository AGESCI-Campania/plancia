# apps/helpdesk/views.py
"""Viste helpdesk. Vedi docs sez. 13."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from apps.helpdesk import services
from apps.helpdesk.models import StatoTicket, Ticket

_STAFF_RUOLI = services.STAFF_HELPDESK


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "helpdesk/list.html"
    context_object_name = "ticket_list"
    paginate_by = 25

    def get_queryset(self):
        qs = services.ticket_visibili(self.request.user)
        stato = self.request.GET.get("stato")
        if stato in StatoTicket.values:
            qs = qs.filter(stato=stato)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_items"] = [{"label": "Home", "url": "/"}, {"label": "Helpdesk", "url": None}]
        ctx["stati"] = StatoTicket.choices
        ctx["stato_corrente"] = self.request.GET.get("stato", "")
        ctx["is_staff_helpdesk"] = self.request.user.ruolo in _STAFF_RUOLI
        return ctx


class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    template_name = "helpdesk/form.html"
    fields = ["oggetto", "corpo", "categoria", "diario"]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["diario"].queryset = services.diari_selezionabili(self.request.user)
        form.fields["diario"].required = False
        return form

    def form_valid(self, form):
        form.instance.aperto_da = self.request.user
        messages.success(self.request, "Ticket aperto con successo.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "helpdesk/detail.html"
    context_object_name = "ticket"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        services.controlla_accesso(self.request.user, obj)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["risposte"] = self.object.risposte.select_related("autore")
        ctx["is_staff_helpdesk"] = self.request.user.ruolo in _STAFF_RUOLI
        return ctx


class RispostaTicketView(LoginRequiredMixin, View):
    """Aggiunge una risposta al ticket."""

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        try:
            services.rispondi(request.user, ticket, request.POST.get("testo", ""))
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("helpdesk:detail", pk=pk)
        messages.success(request, "Risposta aggiunta.")
        return redirect("helpdesk:detail", pk=pk)


class TicketPrendiView(LoginRequiredMixin, View):
    """Staff prende in carico un ticket."""

    def post(self, request, pk):
        if not services.e_staff_helpdesk(request.user):
            raise PermissionDenied
        ticket = get_object_or_404(Ticket, pk=pk)
        try:
            services.prendi_in_carico(request.user, ticket)
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("helpdesk:detail", pk=pk)
        messages.success(request, "Ticket preso in carico.")
        return redirect("helpdesk:detail", pk=pk)


class TicketChiudiView(LoginRequiredMixin, View):
    """Chiude un ticket."""

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        try:
            services.chiudi(request.user, ticket)
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("helpdesk:detail", pk=pk)
        messages.success(request, "Ticket chiuso.")
        return redirect("helpdesk:detail", pk=pk)
