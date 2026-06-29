# apps/evaluations/views.py
"""Viste per la valutazione dei diari. Vedi docs sez. 6."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.diaries.models import Diario
from apps.evaluations.actions import (
    AzioneNonConsentita,
    PermessoNegato,
    assegna_pgv,
    conferma_proposta,
    modifica_valutazione,
    proponi_pgv,
    pubblica_esito,
    pubblica_tutti,
    rigetta_proposta,
    valuta_direttamente,
)
from apps.evaluations.models import EsitoValutazione, Valutazione


class ValutazioneDetailView(LoginRequiredMixin, DetailView):
    """Dettaglio valutazione — visibile solo a PGV assegnato, Incaricato, Segreteria, Admin."""

    model = Valutazione
    template_name = "evaluations/detail.html"
    context_object_name = "valutazione"

    def get_object(self, queryset=None):
        diario = get_object_or_404(Diario, pk=self.kwargs["diario_pk"])
        ruolo = self.request.user.ruolo
        if ruolo in (Ruolo.CSQ, Ruolo.CRP) and not diario.pubblicato_at:
            raise PermissionDenied
        val, _ = Valutazione.objects.get_or_create(diario=diario)
        if ruolo == Ruolo.PGV and not val.assegnazioni_pgv.filter(pgv=self.request.user).exists():
            raise PermissionDenied
        return val

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["diario"] = self.object.diario
        ctx["esiti"] = EsitoValutazione.choices
        ruolo = self.request.user.ruolo
        ctx["puo_valutare_direttamente"] = ruolo in (Ruolo.INCARICATO_EG, Ruolo.ADMIN, Ruolo.SEGRETERIA)
        ctx["puo_proporre"] = ruolo == Ruolo.PGV
        ctx["puo_confermare"] = ruolo in (Ruolo.INCARICATO_EG, Ruolo.ADMIN)
        ctx["puo_pubblicare"] = ruolo in (Ruolo.INCARICATO_EG, Ruolo.ADMIN)
        ctx["pubblicato"] = bool(self.object.diario.pubblicato_at)
        ctx["puo_assegnare_pgv"] = ruolo in (Ruolo.INCARICATO_EG, Ruolo.ADMIN, Ruolo.SEGRETERIA)
        ctx["assegnazioni"] = self.object.assegnazioni_pgv.select_related("pgv")
        return ctx


class AssegnaPGVView(RuoloRequiredMixin, View):
    """Assegna un membro PGV a un diario."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN, Ruolo.SEGRETERIA)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        pgv_pk = request.POST.get("pgv_pk")
        if not pgv_pk:
            messages.error(request, "Seleziona un membro PGV.")
            return redirect("evaluations:detail", diario_pk=diario.pk)

        from apps.accounts.models import User
        pgv = get_object_or_404(User, pk=pgv_pk, ruolo=Ruolo.PGV)
        try:
            created, _ = assegna_pgv(diario, pgv, request.user)
        except AzioneNonConsentita as e:
            messages.error(request, str(e))
            return redirect("evaluations:detail", diario_pk=diario.pk)
        if created:
            messages.success(request, f"Diario assegnato a {pgv.get_full_name() or pgv.email}.")
        else:
            messages.info(request, "Il diario era già assegnato a questo PGV.")
        return redirect("evaluations:detail", diario_pk=diario.pk)


class ValutaDirettamenteView(RuoloRequiredMixin, View):
    """Incaricato EG/Admin valuta direttamente senza passare per PGV."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN, Ruolo.SEGRETERIA)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        esito = request.POST.get("esito", "")
        note = request.POST.get("note", "")
        try:
            valuta_direttamente(diario, esito, note, request.user)
            messages.success(request, "Valutazione registrata.")
        except AzioneNonConsentita as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class PropostaValutazioneView(RuoloRequiredMixin, View):
    """Membro PGV propone Approvata/Non approvata."""

    ruoli_ammessi = (Ruolo.PGV,)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        esito = request.POST.get("esito", "")
        note = request.POST.get("note", "")
        try:
            proponi_pgv(diario, esito, note, request.user)
            messages.success(request, "Proposta registrata. In attesa di conferma dall'Incaricato.")
        except PermessoNegato:
            raise PermissionDenied from None
        except AzioneNonConsentita as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class ConfermaPropostaView(RuoloRequiredMixin, View):
    """Incaricato EG/Admin conferma la proposta PGV."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        note = request.POST.get("note", "")
        try:
            conferma_proposta(diario, note, request.user)
            messages.success(request, "Proposta confermata.")
        except AzioneNonConsentita as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class RigettaPropostaView(RuoloRequiredMixin, View):
    """Incaricato EG/Admin rigetta la proposta PGV."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        try:
            rigetta_proposta(diario, request.user)
            messages.success(request, "Proposta rigettata. Il diario torna in valutazione.")
        except AzioneNonConsentita as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class ModificaValutazioneView(RuoloRequiredMixin, View):
    """Incaricato modifica l'esito prima della pubblicazione."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        esito = request.POST.get("esito", "")
        note = request.POST.get("note", "")
        try:
            modifica_valutazione(diario, esito, note, request.user)
            messages.success(request, "Valutazione aggiornata.")
        except AzioneNonConsentita as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class PubblicaEsitoView(RuoloRequiredMixin, View):
    """Pubblica l'esito di un singolo diario."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        try:
            pubblica_esito(diario, request.user)
            messages.success(request, "Esito pubblicato.")
        except AzioneNonConsentita as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class PubblicaEsitiEdizioneView(RuoloRequiredMixin, View):
    """Pubblica tutti gli esiti confermati di un'edizione (o per scadenza)."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, edizione_pk):
        from apps.editions.models import Edizione

        edizione = get_object_or_404(Edizione, pk=edizione_pk)
        scadenza = request.POST.get("scadenza") or None
        try:
            count = pubblica_tutti(edizione, request.user, scadenza)
            messages.success(request, f"Pubblicati {count} esiti.")
        except AzioneNonConsentita as e:
            messages.error(request, str(e))
        return redirect("editions:detail", pk=edizione.pk)
