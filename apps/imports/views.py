# apps/imports/views.py
"""Schermata di riconciliazione manuale import. Vedi docs sez. 14."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.imports import services
from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch, TipoImport

_STAFF = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)


class ImportLogListView(RuoloRequiredMixin, ListView):
    model = LogImportazione
    template_name = "imports/log_list.html"
    context_object_name = "log_list"
    ruoli_ammessi = _STAFF
    paginate_by = 30
    ordering = ["-creato_at"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.editions.models import Edizione
        ctx["edizioni_import"] = Edizione.objects.order_by("-anno")
        return ctx


class ImportLogDetailView(RuoloRequiredMixin, DetailView):
    model = LogImportazione
    template_name = "imports/log_detail.html"
    context_object_name = "log"
    ruoli_ammessi = _STAFF

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["righe_da_riconciliare"] = self.object.righe.filter(
            stato_match=StatoMatch.DA_RICONCILIARE
        ).order_by("numero")
        ctx["righe_scartate"] = self.object.righe.filter(
            stato_match=StatoMatch.SCARTATA
        ).order_by("numero")
        ctx["e_squadriglie"] = self.object.tipo == TipoImport.SQUADRIGLIE
        return ctx


class ScartiCsvView(RuoloRequiredMixin, View):
    """Scarica le righe scartate di un LogImportazione come CSV (UTF-8 con BOM per Excel)."""

    ruoli_ammessi = _STAFF

    def get(self, request, pk):
        log = get_object_or_404(LogImportazione, pk=pk)
        response = HttpResponse(services.csv_scarti(log), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="scarti_import_{pk}.csv"'
        return response


class ScartiCsvViewerView(RuoloRequiredMixin, View):
    """GET /imports/<pk>/scarti/visualizza/ — pagina viewer PWA-friendly per il CSV scarti."""

    ruoli_ammessi = _STAFF

    def get(self, request, pk):
        from urllib.parse import urlparse

        from django.shortcuts import render
        from django.urls import reverse

        log = get_object_or_404(LogImportazione, pk=pk)
        referer = request.META.get("HTTP_REFERER", "")
        back_url = reverse("imports:log_detail", args=[pk])
        if referer:
            parsed = urlparse(referer)
            if parsed.path:
                back_url = parsed.path + (("?" + parsed.query) if parsed.query else "")

        return render(request, "shared/file_viewer.html", {
            "file_url": reverse("imports:scarti_csv", args=[pk]),
            "file_filename": f"scarti_import_{pk}.csv",
            "file_mime": "text/csv",
            "back_url": back_url,
            "page_title": f"Scarti import #{pk}",
            "breadcrumb_items": [
                {"label": "Home", "url": "/"},
                {"label": "Import", "url": reverse("imports:log_list")},
                {"label": f"Import #{pk}", "url": reverse("imports:log_detail", args=[pk])},
                {"label": "Scarti CSV", "url": None},
            ],
        })


class RiconciliaRigaView(RuoloRequiredMixin, View):
    """Associa manualmente una RigaImportazione(da_riconciliare) al Socio(capo) corretto."""

    ruoli_ammessi = _STAFF

    def post(self, request, riga_pk):
        riga = get_object_or_404(
            RigaImportazione, pk=riga_pk, stato_match=StatoMatch.DA_RICONCILIARE
        )
        socio_pk = request.POST.get("socio_pk")
        if not socio_pk:
            messages.error(request, "Seleziona un Socio capo.")
            return redirect("imports:log_detail", pk=riga.log_id)

        from apps.org.models import Categoria, Socio

        socio = get_object_or_404(Socio, pk=socio_pk, categoria=Categoria.CAPO)
        services.riconcilia_riga(riga, socio)
        messages.success(request, f"Riga {riga.numero} riconciliata con {socio}.")
        return redirect("imports:log_detail", pk=riga.log_id)


class RiprovaAnomalieView(RuoloRequiredMixin, View):
    """Riprova automaticamente le anomalie Capo Reparto di un log squadriglie.

    Logica in `apps.imports.services.riprova_anomalie`.
    """

    ruoli_ammessi = _STAFF

    def post(self, request, log_pk):
        log = get_object_or_404(LogImportazione, pk=log_pk, tipo=TipoImport.SQUADRIGLIE)
        risolte, ancora_aperte = services.riprova_anomalie(log)
        testo = services.messaggio_riprova(risolte, ancora_aperte)
        if risolte:
            messages.success(request, testo)
        elif ancora_aperte:
            messages.warning(request, testo)
        else:
            messages.info(request, testo)
        return redirect("imports:log_detail", pk=log_pk)
