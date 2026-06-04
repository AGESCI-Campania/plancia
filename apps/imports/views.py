# apps/imports/views.py
"""Schermata di riconciliazione manuale import. Vedi docs sez. 14."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch, TipoImport

_STAFF = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)


class ImportLogListView(RuoloRequiredMixin, ListView):
    model = LogImportazione
    template_name = "imports/log_list.html"
    context_object_name = "log_list"
    ruoli_ammessi = _STAFF
    paginate_by = 30
    ordering = ["-creato_at"]


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
        ctx["e_squadriglie"] = self.object.tipo == TipoImport.SQUADRIGLIE
        return ctx


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

        _aggiorna_diario_crp(riga, socio)

        riga.socio_match = socio
        riga.stato_match = StatoMatch.OK
        riga.note = f"Riconciliato manualmente → {socio}"
        riga.save(update_fields=["socio_match", "stato_match", "note"])

        log = riga.log
        log.da_riconciliare = max(0, (log.da_riconciliare or 0) - 1)
        log.ok = (log.ok or 0) + 1
        log.save(update_fields=["da_riconciliare", "ok"])

        messages.success(request, f"Riga {riga.numero} riconciliata con {socio}.")
        return redirect("imports:log_detail", pk=riga.log_id)


class RiprovaAnomalieView(RuoloRequiredMixin, View):
    """Riprova automaticamente le anomalie CRP di un log squadriglie.

    Cerca di abbinare il CRP per email/nome tra i Socio(capo) attualmente
    presenti nel DB, senza re-importare il file. Da usare dopo un nuovo
    import capi o dopo l'inserimento manuale del capo mancante.
    """

    ruoli_ammessi = _STAFF

    def post(self, request, log_pk):
        log = get_object_or_404(LogImportazione, pk=log_pk, tipo=TipoImport.SQUADRIGLIE)
        righe = log.righe.filter(stato_match=StatoMatch.DA_RICONCILIARE)

        if not righe.exists():
            messages.info(request, "Nessuna anomalia da riprovare.")
            return redirect("imports:log_detail", pk=log_pk)

        from apps.imports.management.commands.import_squadriglie import _parse_crp_nome, trova_crp

        risolte = 0
        ancora_aperte = 0

        for riga in righe:
            dati = riga.dati_grezzi
            crp_email = (dati.get("EmailReferente") or "").strip()
            crp_raw = (dati.get("NomeReferente") or "").strip()
            crp_cognome, crp_nome = _parse_crp_nome(crp_raw) if crp_raw else ("", "")

            # Cerca solo tra i Socio(capo) NON provvisori
            crp_socio, trovato = trova_crp(crp_email, crp_cognome, crp_nome)
            if trovato and getattr(crp_socio, "provvisorio", False):
                trovato = False
                crp_socio = None
            if trovato:
                _aggiorna_diario_crp(riga, crp_socio)
                riga.socio_match = crp_socio
                riga.stato_match = StatoMatch.OK
                riga.note = f"Riconciliato automaticamente (riprova) → {crp_socio}"
                riga.save(update_fields=["socio_match", "stato_match", "note"])
                risolte += 1
            else:
                ancora_aperte += 1

        # Aggiorna i contatori del log
        log.da_riconciliare = ancora_aperte
        log.ok = (log.ok or 0) + risolte
        log.save(update_fields=["da_riconciliare", "ok"])

        if risolte:
            messages.success(
                request,
                f"Risolte {risolte} anomali{'a' if risolte == 1 else 'e'}."
                + (
                    f" Ne restano {ancora_aperte} da riconciliare manualmente."
                    if ancora_aperte
                    else ""
                ),
            )
        else:
            messages.warning(
                request,
                f"Nessuna anomalia risolta. I {ancora_aperte} CRP non sono ancora presenti nel DB. "
                "Eseguire l'import capi o inserire i capi mancanti, poi riprovare.",
            )

        return redirect("imports:log_detail", pk=log_pk)


# ---------------------------------------------------------------------------
# Helper condiviso
# ---------------------------------------------------------------------------


def _aggiorna_diario_crp(riga: RigaImportazione, crp_socio) -> None:
    """Sostituisce il CRP sul Diario associato alla riga con il Socio(capo) reale.

    Gestisce tre casi:
    - Diario con crp=None (vecchio comportamento)
    - Diario con crp provvisorio (nuovo: creato durante import)
    In entrambi i casi trasferisce l'eventuale User dal provvisorio al Socio reale
    e cancella il Socio provvisorio.
    """
    log = riga.log
    if not log.edizione_id:
        return
    dati = riga.dati_grezzi
    codice_csq = (dati.get("Codice") or "").strip()
    if not codice_csq:
        return

    from django.db.models import Q

    from apps.diaries.models import Diario
    from apps.org.models import Socio

    csq = Socio.objects.filter(codice_socio=codice_csq).first()
    if not csq:
        return

    diari_da_aggiornare = Diario.objects.filter(
        edizione_id=log.edizione_id,
        csq=csq,
    ).filter(Q(crp__isnull=True) | Q(crp__provvisorio=True))

    # Raccogli i CRP provvisori prima di sovrascriverli
    provvisori = list(
        Socio.objects.filter(
            provvisorio=True,
            diari_crp__in=diari_da_aggiornare,
        ).distinct()
    )

    diari_da_aggiornare.update(crp=crp_socio)

    # Trasferisci l'eventuale User e cancella i Socio provvisori
    for prov in provvisori:
        _trasferisci_utente_provvisorio(prov, crp_socio)


def _trasferisci_utente_provvisorio(provvisorio, reale) -> None:
    """Sposta l'account utente dal Socio provvisorio a quello reale, poi elimina il provvisorio."""
    if hasattr(provvisorio, "utente") and provvisorio.utente is not None:
        utente = provvisorio.utente
        utente.socio = reale
        utente.save(update_fields=["socio"])
    provvisorio.delete()
