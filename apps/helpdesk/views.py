# apps/helpdesk/views.py
"""Viste helpdesk. Vedi docs sez. 13."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from apps.accounts.models import Ruolo
from apps.helpdesk.models import CategoriaTicket, RispostaTicket, StatoTicket, Ticket


_STAFF_RUOLI = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "helpdesk/list.html"
    context_object_name = "ticket_list"
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = Ticket.objects.select_related("aperto_da", "assegnato_a", "diario")
        if user.ruolo not in _STAFF_RUOLI and not user.is_superuser:
            qs = qs.filter(aperto_da=user)
        stato = self.request.GET.get("stato")
        if stato in StatoTicket.values:
            qs = qs.filter(stato=stato)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
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
        from apps.diaries.models import Diario
        user = self.request.user
        if user.ruolo == Ruolo.CSQ and hasattr(user, "socio") and user.socio:
            form.fields["diario"].queryset = Diario.objects.filter(csq=user.socio)
        elif user.ruolo == Ruolo.CRP and hasattr(user, "socio") and user.socio:
            form.fields["diario"].queryset = Diario.objects.filter(
                squadriglia__reparto__in=user.socio.reparti_capo.all()
            )
        else:
            form.fields["diario"].queryset = Diario.objects.none()
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
        user = self.request.user
        if obj.aperto_da != user and user.ruolo not in _STAFF_RUOLI and not user.is_superuser:
            raise PermissionDenied
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
        user = request.user
        if ticket.aperto_da != user and user.ruolo not in _STAFF_RUOLI and not user.is_superuser:
            raise PermissionDenied
        testo = request.POST.get("testo", "").strip()
        if not testo:
            messages.error(request, "La risposta non può essere vuota.")
            return redirect("helpdesk:detail", pk=pk)
        RispostaTicket.objects.create(ticket=ticket, autore=user, testo=testo)
        if ticket.stato == StatoTicket.APERTO and user.ruolo in _STAFF_RUOLI:
            ticket.prendi_in_carico(user)
        messages.success(request, "Risposta aggiunta.")
        return redirect("helpdesk:detail", pk=pk)


class TicketPrendiView(LoginRequiredMixin, View):
    """Staff prende in carico un ticket."""

    def post(self, request, pk):
        if request.user.ruolo not in _STAFF_RUOLI and not request.user.is_superuser:
            raise PermissionDenied
        ticket = get_object_or_404(Ticket, pk=pk)
        ticket.prendi_in_carico(request.user)
        messages.success(request, "Ticket preso in carico.")
        return redirect("helpdesk:detail", pk=pk)


class TicketChiudiView(LoginRequiredMixin, View):
    """Chiude un ticket."""

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        if ticket.aperto_da != request.user and request.user.ruolo not in _STAFF_RUOLI:
            raise PermissionDenied
        ticket.chiudi(request.user)
        messages.success(request, "Ticket chiuso.")
        return redirect("helpdesk:detail", pk=pk)
