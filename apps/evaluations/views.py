# apps/evaluations/views.py
"""Viste per la valutazione dei diari. Vedi docs sez. 6."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, UpdateView

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.diaries.models import Diario, StatoDiario
from apps.evaluations.models import AssegnazionePGV, EsitoValutazione, Valutazione


def _get_valutazione_or_create(diario) -> Valutazione:
    val, _ = Valutazione.objects.get_or_create(diario=diario)
    return val


class ValutazioneDetailView(LoginRequiredMixin, DetailView):
    """Dettaglio valutazione — visibile solo a PGV assegnato, Incaricato, Segreteria, Admin."""

    model = Valutazione
    template_name = "evaluations/detail.html"
    context_object_name = "valutazione"

    def get_object(self, queryset=None):
        diario = get_object_or_404(Diario, pk=self.kwargs["diario_pk"])
        ruolo = self.request.user.ruolo
        if ruolo in (Ruolo.CSQ, Ruolo.CRP):
            if not diario.pubblicato_at:
                raise PermissionDenied
        val = _get_valutazione_or_create(diario)
        if ruolo == Ruolo.PGV:
            if not val.assegnazioni_pgv.filter(pgv=self.request.user).exists():
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
        val = _get_valutazione_or_create(diario)
        _, created = AssegnazionePGV.objects.get_or_create(
            valutazione=val, pgv=pgv, defaults={"assegnato_da": request.user}
        )
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
        if diario.stato not in (StatoDiario.IN_VALUTAZIONE, StatoDiario.IN_REVISIONE):
            messages.error(request, "Il diario non è in stato valutabile.")
            return redirect("evaluations:detail", diario_pk=diario.pk)

        esito = request.POST.get("esito")
        note = request.POST.get("note", "")
        if esito not in EsitoValutazione.values:
            messages.error(request, "Esito non valido.")
            return redirect("evaluations:detail", diario_pk=diario.pk)

        val = _get_valutazione_or_create(diario)
        val.valuta_direttamente(request.user, esito, note)
        messages.success(request, "Valutazione registrata.")
        return redirect("evaluations:detail", diario_pk=diario.pk)


class PropostaValutazioneView(RuoloRequiredMixin, View):
    """Membro PGV propone Approvata/Non approvata."""

    ruoli_ammessi = (Ruolo.PGV,)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        try:
            val_check = diario.valutazione
        except Valutazione.DoesNotExist:
            raise PermissionDenied
        if not val_check.assegnazioni_pgv.filter(pgv=request.user).exists():
            raise PermissionDenied

        esito = request.POST.get("esito")
        note = request.POST.get("note", "")
        if esito == EsitoValutazione.MAGGIORI_INFO:
            messages.error(request, "Maggiori informazioni non può essere proposto da un PGV.")
            return redirect("evaluations:detail", diario_pk=diario.pk)
        if esito not in EsitoValutazione.values:
            messages.error(request, "Esito non valido.")
            return redirect("evaluations:detail", diario_pk=diario.pk)

        val = _get_valutazione_or_create(diario)
        val.proponi_pgv(request.user, esito, note)
        messages.success(request, "Proposta registrata. In attesa di conferma dall'Incaricato.")
        return redirect("evaluations:detail", diario_pk=diario.pk)


class ConfermaPropostaView(RuoloRequiredMixin, View):
    """Incaricato EG/Admin conferma la proposta PGV."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        val = get_object_or_404(Valutazione, diario=diario)
        note = request.POST.get("note", "")
        try:
            val.conferma(request.user, note)
            messages.success(request, "Proposta confermata.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class RigettaPropostaView(RuoloRequiredMixin, View):
    """Incaricato EG/Admin rigetta la proposta PGV."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        val = get_object_or_404(Valutazione, diario=diario)
        try:
            val.rigetta_proposta(request.user)
            messages.success(request, "Proposta rigettata. Il diario torna in valutazione.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class ModificaValutazioneView(RuoloRequiredMixin, View):
    """Incaricato modifica l'esito prima della pubblicazione."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        val = get_object_or_404(Valutazione, diario=diario)
        esito = request.POST.get("esito")
        note = request.POST.get("note", "")
        try:
            val.modifica(request.user, esito, note)
            messages.success(request, "Valutazione aggiornata.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("evaluations:detail", diario_pk=diario.pk)


class PubblicaEsitoView(RuoloRequiredMixin, View):
    """Pubblica l'esito di un singolo diario."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, diario_pk):
        diario = get_object_or_404(Diario, pk=diario_pk)
        val = get_object_or_404(Valutazione, diario=diario)
        if not val.esito:
            messages.error(request, "Nessun esito da pubblicare.")
            return redirect("evaluations:detail", diario_pk=diario.pk)
        from django.utils import timezone
        diario.pubblicato_at = timezone.now()
        diario.save(update_fields=["pubblicato_at"])
        messages.success(request, "Esito pubblicato.")
        return redirect("evaluations:detail", diario_pk=diario.pk)


class PubblicaEsitiEdizioneView(RuoloRequiredMixin, View):
    """Pubblica tutti gli esiti confermati di un'edizione (o per scadenza)."""

    ruoli_ammessi = (Ruolo.INCARICATO_EG, Ruolo.ADMIN)

    def post(self, request, edizione_pk):
        from apps.editions.models import Edizione
        from apps.evaluations.models import StatoValutazione
        from django.utils import timezone

        edizione = get_object_or_404(Edizione, pk=edizione_pk)
        scadenza = request.POST.get("scadenza")

        qs = edizione.diari.filter(
            pubblicato_at__isnull=True,
            valutazione__stato=StatoValutazione.CONFERMATA,
            valutazione__esito__isnull=False,
        )
        if scadenza:
            qs = qs.filter(scadenza_riferimento=scadenza)

        count = 0
        ts = timezone.now()
        for diario in qs.select_related("valutazione"):
            diario.pubblicato_at = ts
            diario.save(update_fields=["pubblicato_at"])
            count += 1

        messages.success(request, f"Pubblicati {count} esiti.")
        return redirect("editions:detail", pk=edizione.pk)
