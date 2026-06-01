# apps/notifications/views.py
"""Viste per attivazione inviti e invio notifiche. Vedi docs sez. 8."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.notifications.models import Invito, StatoInvito


class AttivazoneInvitoView(View):
    """Attiva il token di un invito: autentica l'utente e lo reindirizza al diario."""

    def get(self, request, token):
        invito = get_object_or_404(Invito, token=token)

        if invito.stato == StatoInvito.ATTIVATO:
            messages.info(request, "Questo invito è già stato attivato.")
            return redirect("diaries:list")

        if invito.stato == StatoInvito.SCADUTO:
            messages.error(request, "Questo invito è scaduto. Contatta la segreteria per un nuovo invito.")
            return redirect("account_login")

        invito.attiva()
        utente = invito.utente
        utente.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, utente)
        messages.success(request, f"Benvenuto/a, {utente.get_full_name() or utente.email}!")

        if invito.diario:
            return redirect("diaries:detail", pk=invito.diario.pk)
        return redirect("diaries:list")


class ReinvioInvitoView(RuoloRequiredMixin, View):
    """Reinvia un invito (crea un nuovo token, invalida il vecchio)."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request, pk):
        invito = get_object_or_404(Invito, pk=pk)
        from apps.notifications.service import reinvia_invito
        nuovo = reinvia_invito(invito)
        messages.success(request, f"Invito reinviato a {invito.utente.email}.")
        if invito.diario:
            return redirect("diaries:detail", pk=invito.diario.pk)
        return redirect("diaries:list")


class InvioInvitiBulkView(RuoloRequiredMixin, View):
    """Invia tutti gli inviti mancanti per un diario (POST da dettaglio diario)."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request, diario_pk):
        from apps.diaries.models import Diario
        from apps.notifications.tasks import task_invia_inviti_bulk

        diario = get_object_or_404(Diario, pk=diario_pk)
        ruoli = request.POST.getlist("ruoli") or ["csq", "crp"]
        task_invia_inviti_bulk.delay(diario.pk, ruoli)
        messages.success(request, "Inviti accodati per l'invio.")
        return redirect("diaries:detail", pk=diario.pk)
