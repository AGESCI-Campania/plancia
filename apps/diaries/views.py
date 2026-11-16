# apps/diaries/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView, View

from apps.accounts.models import Ruolo
from apps.diaries import permessi
from apps.diaries import service as diari_service
from apps.diaries.forms import (
    AnagraficaForm,
    BrevettoFormSet,
    ImpresaForm,
    MembroSqFormSet,
    MissioneForm,
    PostoAzioneFormSet,
    PresentazioneForm,
    RelazioneFinaleForm,
    SpecialitaFormSet,
)
from apps.diaries.models import (
    Allegato,
    Anagrafica,
    Diario,
    Impresa,
    Missione,
    Presentazione,
    RelazioneFinale,
    StatoDiario,
    TipoDiario,
    TipoEsito,
)

# Regole e costanti condivise con l'API: apps/diaries/permessi.py e apps/diaries/service.py
_STATI_PRIMA_INVIO = permessi.STATI_PRIMA_INVIO
_STATI_PDF = permessi.STATI_PDF


# ---------------------------------------------------------------------------
# Mixin: accesso scoped al Diario
# ---------------------------------------------------------------------------


class DiarioAccessMixin(LoginRequiredMixin):
    """Carica il Diario e verifica che l'utente possa accedervi."""

    def _get_diario(self, pk: int) -> Diario:
        diario = get_object_or_404(
            Diario.objects.select_related("edizione", "squadriglia", "csq", "crp"),
            pk=pk,
        )
        from apps.diaries.visibility import diari_visibili

        # Visibilità: unica fonte di verità (Pattuglia GV solo sui diari assegnati)
        if not diari_visibili(self.request.user).filter(pk=diario.pk).exists():
            raise PermissionDenied
        return diario

    def _puo_editare(self, diario: Diario) -> bool:
        """True se l'utente può editare i moduli CSQ (1-5) del diario."""
        return permessi.puo_modificare_moduli(self.request.user, diario)

    def _inizia_se_necessario(self, diario: Diario) -> None:
        """Transita NON_INIZIATO → IN_COMPILAZIONE al primo salvataggio del CSQ."""
        diari_service.inizia_se_necessario(diario)

    def _puo_editare_relazione(self, diario: Diario) -> bool:
        """True se il Capo Reparto può compilare la relazione finale (modulo 6)."""
        return permessi.puo_modificare_relazione(self.request.user, diario)


# ---------------------------------------------------------------------------
# Lista e dettaglio
# ---------------------------------------------------------------------------


class DiarioListView(LoginRequiredMixin, ListView):
    template_name = "diaries/list.html"
    context_object_name = "diari"

    def get_queryset(self):
        from apps.diaries.visibility import diari_visibili
        return diari_visibili(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_items"] = [{"label": "Home", "url": "/"}, {"label": "Diari", "url": None}]
        from apps.editions.models import Edizione

        ctx["edizioni"] = Edizione.objects.all()
        edizione_pk = self.request.GET.get("edizione")
        if edizione_pk:
            ctx["diari"] = ctx["diari"].filter(edizione_id=edizione_pk)
            ctx["edizione_sel"] = edizione_pk
        diari = list(ctx["diari"])
        ctx["zone"] = sorted({d.squadriglia.reparto.gruppo.zona.nome for d in diari})
        ctx["gruppi"] = sorted({d.squadriglia.reparto.gruppo.nome for d in diari})
        ctx["specialita_list"] = sorted({
            d.anagrafica.specialita
            for d in diari
            if hasattr(d, "anagrafica") and d.anagrafica.specialita
        })
        ctx["stati_choices"] = StatoDiario.choices
        ctx["tipi_choices"] = TipoDiario.choices
        return ctx


class DiarioDetailView(DiarioAccessMixin, DetailView):
    model = Diario
    template_name = "diaries/detail.html"
    context_object_name = "diario"

    def get_object(self, queryset=None):
        return self._get_diario(self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        diario = self.object
        from django.urls import reverse
        ctx["breadcrumb_items"] = [
            {"label": "Home", "url": "/"},
            {"label": "Diari", "url": reverse("diaries:list")},
            {"label": str(diario.squadriglia), "url": None},
        ]
        user = self.request.user
        is_csq = user.ruolo == Ruolo.CSQ
        ctx["puo_editare"] = self._puo_editare(diario)
        ctx["is_csq"] = is_csq
        # Relazione finale: mai visibile al CSQ (docs sez. 5)
        ctx["mostra_relazione"] = permessi.puo_vedere_relazione(user)
        # Completezza moduli CSQ
        ctx["moduli_csq_completi"] = diario.moduli_csq_completi
        # Moduli esistenti
        ctx["has_anagrafica"] = hasattr(diario, "anagrafica")
        ctx["has_presentazione"] = hasattr(diario, "presentazione")
        ctx["imprese"] = diario.imprese.all()
        ctx["has_imp2"] = diario.imprese.filter(numero=2).exists()
        ctx["has_missione"] = hasattr(diario, "missione")
        ctx["has_relazione"] = hasattr(diario, "relazione_finale")
        # Capo Squadriglia può inviare la propria parte (→ Relazione finale)
        ctx["puo_inviare_csq"] = permessi.puo_inviare_csq(user, diario)
        # Capo Reparto può inviare il diario allo staff (→ Inviato)
        ctx["puo_inviare"] = permessi.puo_inviare(user, diario)
        ctx["puo_riapire"] = permessi.puo_riaprire(user, diario)
        # Cambio CSQ: CRP quando NON_INIZIATO/IN_COMPILAZIONE; admin/seg/iabr prima dell'invio
        ctx["puo_cambiare_csq"] = permessi.puo_cambiare_csq(user, diario)
        # Cambio CRP: solo admin/seg/iabr prima dell'invio
        ctx["puo_cambiare_crp"] = permessi.puo_cambiare_crp(user, diario)
        # Dilazione (solo staff, solo prima dell'invio allo staff)
        if permessi.puo_concedere_dilazione(user, diario):
            from apps.editions.forms import DilazioneForm
            ctx["dilazione_form"] = DilazioneForm()
        ctx["puo_pdf"] = permessi.pdf_disponibile_nello_stato(diario)
        # Allegati per modulo (conteggio + anteprime foto nel detail)
        allegati_all = list(diario.allegati.all())
        ctx["allegati_impresa_1"] = [a for a in allegati_all if a.modulo == "impresa_1"]
        ctx["allegati_impresa_2"] = [a for a in allegati_all if a.modulo == "impresa_2"]
        ctx["allegati_missione"] = [a for a in allegati_all if a.modulo == "missione"]
        ctx["puo_editare_relazione"] = self._puo_editare_relazione(diario)
        # Eliminazione allegati: ammessa fino all'invio del diario allo staff
        ctx["puo_eliminare_allegati"] = permessi.puo_eliminare_allegati(user, diario)
        return ctx


# ---------------------------------------------------------------------------
# Modulo 1 — Anagrafica
# ---------------------------------------------------------------------------


class AnagraficaUpdateView(DiarioAccessMixin, View):
    template_name = "diaries/modules/anagrafica.html"

    def _setup(self, pk):
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            raise PermissionDenied
        anagrafica, _ = Anagrafica.objects.get_or_create(diario=diario)
        return diario, anagrafica

    def get(self, request, pk):
        from django.shortcuts import render
        from django.urls import reverse

        diario, anagrafica = self._setup(pk)
        form = AnagraficaForm(instance=anagrafica, utente=request.user, diario=diario)
        return render(request, self.template_name, {
            "form": form,
            "diario": diario,
            "breadcrumb_items": [
                {"label": "Home", "url": "/"},
                {"label": "Diari", "url": reverse("diaries:list")},
                {"label": str(diario.squadriglia), "url": reverse("diaries:detail", args=[pk])},
                {"label": "Anagrafica", "url": None},
            ],
        })

    def post(self, request, pk):
        from django.shortcuts import render

        diario, anagrafica = self._setup(pk)
        self._inizia_se_necessario(diario)
        form = AnagraficaForm(
            request.POST, instance=anagrafica, utente=request.user, diario=diario
        )
        if form.is_valid():
            form.save()
            diari_service.incrementa_versione(anagrafica)

            # Salva tipo diario
            diario.tipo = form.cleaned_data["tipo_diario"]
            diario.save(update_fields=["tipo"])

            # Rinomina squadriglia se cambiata
            nuovo_nome = form.cleaned_data.get("squadriglia_nome", "").strip()
            if nuovo_nome and nuovo_nome != diario.squadriglia.nome:
                self._rinomina_squadriglia(diario, nuovo_nome)

            messages.success(request, "Anagrafica salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "diario": diario})

    @staticmethod
    def _rinomina_squadriglia(diario, nuovo_nome: str) -> None:
        """Rinomina la squadriglia nel DB e le cartelle Drive del diario (servizio condiviso)."""
        diari_service.rinomina_squadriglia(diario, nuovo_nome)


# ---------------------------------------------------------------------------
# Modulo 2 — Presentazione
# ---------------------------------------------------------------------------


class PresentazioneUpdateView(DiarioAccessMixin, View):
    template_name = "diaries/modules/presentazione.html"

    def _setup(self, pk):
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            raise PermissionDenied
        presentazione, _ = Presentazione.objects.get_or_create(diario=diario)
        return diario, presentazione

    def get(self, request, pk):
        from django.shortcuts import render

        diario, presentazione = self._setup(pk)
        form = PresentazioneForm(instance=presentazione)
        formset = MembroSqFormSet(instance=presentazione)
        return render(
            request, self.template_name, {"form": form, "formset": formset, "diario": diario}
        )

    def post(self, request, pk):
        from django.shortcuts import render

        diario, presentazione = self._setup(pk)
        self._inizia_se_necessario(diario)
        form = PresentazioneForm(request.POST, instance=presentazione)
        formset = MembroSqFormSet(request.POST, instance=presentazione)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            diari_service.incrementa_versione(presentazione)
            messages.success(request, "Presentazione salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(
            request, self.template_name, {"form": form, "formset": formset, "diario": diario}
        )


# ---------------------------------------------------------------------------
# Moduli 3/4 — Imprese
# ---------------------------------------------------------------------------


class ImpresaUpdateView(DiarioAccessMixin, View):
    template_name = "diaries/modules/impresa.html"

    def _setup(self, pk, numero):
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            raise PermissionDenied
        # Modulo 4 (2ª impresa): non obbligatorio per Rinnovo ma compilabile
        impresa, _ = Impresa.objects.get_or_create(diario=diario, numero=numero)
        return diario, impresa

    def _ctx(self, diario, impresa, numero, form, posti_fs, specialita_fs, brevetti_fs):
        modulo_key = f"impresa_{numero}"
        allegati = list(diario.allegati.filter(modulo=modulo_key))
        puo_eliminare = diario.stato in (
            StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE, StatoDiario.RELAZIONE_FINALE,
        )
        return {
            "form": form,
            "posti_fs": posti_fs,
            "specialita_fs": specialita_fs,
            "brevetti_fs": brevetti_fs,
            "diario": diario,
            "numero": numero,
            "allegati": allegati,
            "puo_eliminare_allegati": puo_eliminare,
        }

    def get(self, request, pk, numero):
        from django.shortcuts import render

        diario, impresa = self._setup(pk, numero)
        form = ImpresaForm(instance=impresa)
        posti_fs = PostoAzioneFormSet(instance=impresa, prefix="posti")
        specialita_fs = SpecialitaFormSet(
            instance=impresa,
            queryset=impresa.esiti_specialita.filter(tipo=TipoEsito.SPECIALITA),
            prefix="specialita",
        )
        brevetti_fs = BrevettoFormSet(
            instance=impresa,
            queryset=impresa.esiti_specialita.filter(tipo=TipoEsito.BREVETTO),
            prefix="brevetti",
        )
        return render(request, self.template_name,
                      self._ctx(diario, impresa, numero, form, posti_fs, specialita_fs, brevetti_fs))

    def post(self, request, pk, numero):
        from django.shortcuts import render

        diario, impresa = self._setup(pk, numero)
        form = ImpresaForm(request.POST, instance=impresa)
        posti_fs = PostoAzioneFormSet(request.POST, instance=impresa, prefix="posti")
        specialita_fs = SpecialitaFormSet(
            request.POST,
            instance=impresa,
            queryset=impresa.esiti_specialita.filter(tipo=TipoEsito.SPECIALITA),
            prefix="specialita",
        )
        brevetti_fs = BrevettoFormSet(
            request.POST,
            instance=impresa,
            queryset=impresa.esiti_specialita.filter(tipo=TipoEsito.BREVETTO),
            prefix="brevetti",
        )
        self._inizia_se_necessario(diario)
        if (
            form.is_valid()
            and posti_fs.is_valid()
            and specialita_fs.is_valid()
            and brevetti_fs.is_valid()
        ):
            form.save()
            posti_fs.save()
            specialita_fs.save()
            brevetti_fs.save()
            diari_service.incrementa_versione(impresa)
            messages.success(request, f"{numero}ª impresa salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name,
                      self._ctx(diario, impresa, numero, form, posti_fs, specialita_fs, brevetti_fs))


# ---------------------------------------------------------------------------
# Modulo 5 — Missione
# ---------------------------------------------------------------------------


class MissioneUpdateView(DiarioAccessMixin, View):
    template_name = "diaries/modules/missione.html"

    def _setup(self, pk):
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            raise PermissionDenied
        missione, _ = Missione.objects.get_or_create(diario=diario)
        return diario, missione

    def _ctx(self, diario, form):
        allegati = list(diario.allegati.filter(modulo="missione"))
        puo_eliminare = diario.stato in (
            StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE, StatoDiario.RELAZIONE_FINALE,
        )
        return {
            "form": form,
            "diario": diario,
            "allegati": allegati,
            "puo_eliminare_allegati": puo_eliminare,
        }

    def get(self, request, pk):
        from django.shortcuts import render

        diario, missione = self._setup(pk)
        form = MissioneForm(instance=missione)
        return render(request, self.template_name, self._ctx(diario, form))

    def post(self, request, pk):
        from django.shortcuts import render

        diario, missione = self._setup(pk)
        self._inizia_se_necessario(diario)
        form = MissioneForm(request.POST, instance=missione)
        if form.is_valid():
            form.save()
            diari_service.incrementa_versione(missione)
            messages.success(request, "Missione salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name, self._ctx(diario, form))


# ---------------------------------------------------------------------------
# Modulo 6 — Relazione finale CRP
# ---------------------------------------------------------------------------


class RelazioneFinaleUpdateView(DiarioAccessMixin, View):
    template_name = "diaries/modules/relazione.html"

    def _check_permessi(self, diario, user):
        """Verifica accesso e precondizioni; lancia PermissionDenied o redirect se non ok."""
        if not permessi.puo_vedere_relazione(user):
            raise PermissionDenied
        if not self._puo_editare_relazione(diario):
            messages.warning(
                self.request,
                "La relazione del Capo Reparto è disponibile solo dopo che il Capo Squadriglia ha inviato la propria parte.",
            )
            return redirect("diaries:detail", pk=diario.pk)
        return None

    def get(self, request, pk):
        from django.shortcuts import render

        diario = self._get_diario(pk)
        esito = self._check_permessi(diario, request.user)
        if esito is not None:
            return esito
        relazione, _ = RelazioneFinale.objects.get_or_create(diario=diario)
        form = RelazioneFinaleForm(instance=relazione)
        return render(request, self.template_name, {"form": form, "diario": diario})

    def post(self, request, pk):
        from django.shortcuts import render

        diario = self._get_diario(pk)
        esito = self._check_permessi(diario, request.user)
        if esito is not None:
            return esito
        relazione, _ = RelazioneFinale.objects.get_or_create(diario=diario)
        form = RelazioneFinaleForm(request.POST, instance=relazione)
        if form.is_valid():
            form.save()
            diari_service.incrementa_versione(relazione)
            messages.success(request, "Relazione finale salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "diario": diario})


# ---------------------------------------------------------------------------
# Transizioni FSM
# ---------------------------------------------------------------------------


class DiarioInviaView(DiarioAccessMixin, View):
    """Gestisce le due fasi di invio:
    - Capo Squadriglia: IN_COMPILAZIONE → RELAZIONE_FINALE
    - Capo Reparto: RELAZIONE_FINALE → INVIATO
    """

    def post(self, request, pk):
        from apps.evaluations.actions import (
            AzioneNonConsentita,
            PermessoNegato,
            csq_invia,
        )
        from apps.evaluations.actions import (
            invia as action_invia,
        )
        diario = self._get_diario(pk)
        try:
            if diario.stato == StatoDiario.IN_COMPILAZIONE:
                csq_invia(diario, request.user)
                messages.success(
                    request,
                    "Parte del Capo Squadriglia inviata. Il Capo Reparto può ora compilare la relazione finale.",
                )
            elif diario.stato == StatoDiario.RELAZIONE_FINALE:
                action_invia(diario, request.user)
                messages.success(request, "Diario inviato allo staff.")
            else:
                messages.error(request, "Invio non consentito nello stato attuale.")
        except PermessoNegato:
            raise PermissionDenied from None
        except AzioneNonConsentita as exc:
            messages.error(request, str(exc))
        return redirect("diaries:detail", pk=pk)


class DiarioRiapriView(DiarioAccessMixin, View):
    """NON_APPROVATO / MAGGIORI_INFO → IN_COMPILAZIONE (staff only)."""

    def post(self, request, pk):
        from apps.evaluations.actions import AzioneNonConsentita, PermessoNegato, riapri
        diario = self._get_diario(pk)
        try:
            riapri(diario, request.user)
            messages.success(request, "Diario riaperto per integrazioni.")
        except PermessoNegato:
            raise PermissionDenied from None
        except AzioneNonConsentita as exc:
            messages.error(request, str(exc))
        return redirect("diaries:detail", pk=pk)


# ---------------------------------------------------------------------------
# Allegati (foto)
# ---------------------------------------------------------------------------

# Regole e resize in apps/diaries/service.py (condivisi con l'API). `_resize_immagine` resta
# come alias perché importato da `apps/imports/management/commands/import_risposte_eg.py`.
_MIME_CONSENTITI = diari_service.MIME_ALLEGATI_CONSENTITI
_MAX_BYTES = diari_service.MAX_BYTES_ALLEGATO
_resize_immagine = diari_service.ridimensiona_immagine


def _allegato_json(a: Allegato) -> dict:
    return {
        "id": a.pk,
        "nome": a.nome,
        "mime": a.mime,
        "dimensione": a.dimensione,
        "stato_sync": a.stato_sync,
        "url": a.file.url if a.file else None,
    }


def _primo_errore(exc) -> str:
    """Primo messaggio di una ValidationError (per le risposte JSON della PWA)."""
    for messaggi in getattr(exc, "message_dict", {}).values():
        if messaggi:
            return str(messaggi[0])
    return " ".join(str(m) for m in exc.messages)


class DiarioPdfView(DiarioAccessMixin, View):
    """GET /diari/<pk>/pdf/ — serve il PDF dalla cache Drive o avvia la generazione async.

    Il PDF include moduli 1–5 (CSQ) e la Relazione finale CRP (modulo 6).
    Non accessibile ai Capi Squadriglia: il PDF è destinato a CRP, Incaricati e Admin.
    Logica (lock, cache, task) in `apps.diaries.service`, condivisa con l'API.
    """

    def get(self, request, pk):
        diario = self._get_diario(pk)

        # CSQ non ha accesso al PDF (il diario è valutato dai capi, non da chi lo compila)
        if not permessi.puo_scaricare_pdf(request.user):
            messages.error(request, "Il PDF del diario non è disponibile per il Capo Squadriglia.")
            return redirect("diaries:detail", pk=pk)

        # 1. PDF pronto (cache Drive) o, senza Drive, generato al volo
        try:
            pronto = diari_service.contenuto_pdf_pronto(diario)
        except Exception as exc:
            messages.error(request, f"Errore nella generazione del PDF: {exc}")
            return redirect("diaries:detail", pk=pk)
        if pronto is not None:
            content, nome = pronto
            response = HttpResponse(content, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{nome}"'
            response["Content-Length"] = len(content)
            return response

        # 2. Drive configurato ma nessuna cache: avvia il task (rispetta i lock)
        stato, avviato = diari_service.avvia_generazione_pdf(diario, request.user)
        if avviato:
            messages.info(request, stato["messaggio"])
        else:
            messages.warning(request, stato["messaggio"])
        return redirect("diaries:detail", pk=pk)


class DiarioPdfViewerView(DiarioAccessMixin, View):
    """GET /diari/<pk>/pdf/visualizza/ — pagina viewer PWA-friendly per il PDF del diario."""

    def get(self, request, pk):
        from urllib.parse import urlparse

        from django.shortcuts import render
        from django.urls import reverse

        diario = self._get_diario(pk)
        if not permessi.puo_scaricare_pdf(request.user):
            messages.error(request, "Il PDF del diario non è disponibile per il Capo Squadriglia.")
            return redirect("diaries:detail", pk=pk)

        nome = diari_service.nome_pdf(diario)
        referer = request.META.get("HTTP_REFERER", "")
        back_url = reverse("diaries:detail", args=[pk])
        if referer:
            parsed = urlparse(referer)
            if parsed.path:
                back_url = parsed.path + (("?" + parsed.query) if parsed.query else "")

        return render(request, "shared/file_viewer.html", {
            "file_url": reverse("diaries:pdf", args=[pk]),
            "file_filename": nome,
            "file_mime": "application/pdf",
            "back_url": back_url,
            "page_title": f"PDF — {diario.squadriglia.nome}",
            "breadcrumb_items": [
                {"label": "Home", "url": "/"},
                {"label": "Diari", "url": reverse("diaries:list")},
                {"label": str(diario.squadriglia), "url": reverse("diaries:detail", args=[pk])},
                {"label": "PDF", "url": None},
            ],
        })


class AllegatoPreviewView(DiarioAccessMixin, View):
    """GET /diari/<pk>/allegati/<allegato_pk>/preview/ → immagine (Drive o file locale)."""

    def get(self, request, pk, allegato_pk):
        diario = self._get_diario(pk)
        allegato = get_object_or_404(Allegato, pk=allegato_pk, diario=diario)

        if not allegato.mime.startswith("image/"):
            raise Http404
        try:
            contenuto = diari_service.contenuto_allegato(diario, allegato)
        except diari_service.FileNonDisponibile:
            raise Http404 from None
        response = HttpResponse(contenuto, content_type=allegato.mime)
        response["Cache-Control"] = "private, max-age=86400"
        return response


class AllegatoListView(DiarioAccessMixin, View):
    """GET /diari/<pk>/allegati/?modulo=<modulo>  →  {results: [...]}"""

    def get(self, request, pk):
        diario = self._get_diario(pk)
        qs = diario.allegati.all()
        modulo = request.GET.get("modulo", "")
        if modulo:
            qs = qs.filter(modulo=modulo)
        return JsonResponse({"results": [_allegato_json(a) for a in qs]})


class AllegatoUploadView(DiarioAccessMixin, View):
    """POST /diari/<pk>/allegati/upload/  →  {id, nome, ...} (201)"""

    def post(self, request, pk):
        from django.core.exceptions import ValidationError

        diario = self._get_diario(pk)
        try:
            allegato = diari_service.carica_allegato(
                diario, request.user, request.POST.get("modulo", ""), request.FILES.get("file"),
            )
        except PermissionDenied:
            return JsonResponse({"error": "Non autorizzato"}, status=403)
        except ValidationError as exc:
            return JsonResponse({"error": _primo_errore(exc)}, status=400)
        return JsonResponse(_allegato_json(allegato), status=201)


class AllegatoDeleteView(DiarioAccessMixin, View):
    """POST /diari/<pk>/allegati/<allegato_pk>/elimina/  →  {ok: true}"""

    def _puo_eliminare(self, diario) -> bool:
        return permessi.puo_eliminare_allegati(self.request.user, diario)

    def post(self, request, pk, allegato_pk):
        diario = self._get_diario(pk)
        if not self._puo_eliminare(diario):
            return JsonResponse({"error": "Non autorizzato"}, status=403)
        allegato = get_object_or_404(Allegato, pk=allegato_pk, diario=diario)
        diari_service.elimina_allegato(diario, allegato, request.user)
        return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# Cambio Capo Squadriglia
# ---------------------------------------------------------------------------


class CambiaCsqView(DiarioAccessMixin, View):
    """Cambia il Capo Squadriglia di un diario.

    - Capo Reparto del diario: quando NON_INIZIATO o IN_COMPILAZIONE.
    - Admin/Segreteria/IABR: prima dell'invio allo staff.
    Regole in `apps.diaries.permessi.puo_cambiare_csq`, modifica in `service.cambia_csq`.
    """

    template_name = "diaries/cambia_csq.html"

    def _verifica_permessi(self, diario, user) -> None:
        if not permessi.puo_cambiare_csq(user, diario):
            raise PermissionDenied

    def get(self, request, pk):
        from django.shortcuts import render

        diario = self._get_diario(pk)
        self._verifica_permessi(diario, request.user)
        return render(request, self.template_name, {"diario": diario})

    def post(self, request, pk):
        from django.core.exceptions import ValidationError
        from django.shortcuts import render

        diario = self._get_diario(pk)
        self._verifica_permessi(diario, request.user)
        try:
            nuovo_csq, vecchio = diari_service.cambia_csq(
                diario, request.POST.get("socio_pk", "").strip(), request.user,
            )
        except ValidationError as exc:
            messages.error(request, _primo_errore(exc))
            return render(request, self.template_name, {"diario": diario})
        nota = f" (sostituisce {vecchio.cognome} {vecchio.nome})" if vecchio else ""
        messages.success(
            request, f"Capo Squadriglia aggiornato: {nuovo_csq.cognome} {nuovo_csq.nome}{nota}."
        )
        return redirect("diaries:detail", pk=pk)


# ---------------------------------------------------------------------------
# Cambio Capo Reparto (singolo diario)
# ---------------------------------------------------------------------------


class CambiaCrpView(DiarioAccessMixin, View):
    """Admin/Segreteria/IABR: cambia il Capo Reparto referente di un diario (prima dell'invio)."""

    template_name = "diaries/cambia_crp.html"

    def _verifica_permessi(self, diario, user) -> None:
        if not permessi.puo_cambiare_crp(user, diario):
            raise PermissionDenied

    def get(self, request, pk):
        from django.shortcuts import render

        diario = self._get_diario(pk)
        self._verifica_permessi(diario, request.user)
        return render(request, self.template_name, {"diario": diario})

    def post(self, request, pk):
        from django.core.exceptions import ValidationError
        from django.shortcuts import render

        diario = self._get_diario(pk)
        self._verifica_permessi(diario, request.user)
        try:
            nuovo_crp, vecchio = diari_service.cambia_crp(
                diario, request.POST.get("socio_pk", "").strip(), request.user,
            )
        except ValidationError as exc:
            messages.error(request, _primo_errore(exc))
            return render(request, self.template_name, {"diario": diario})
        nota = f" (sostituisce {vecchio.cognome} {vecchio.nome})" if vecchio else ""
        messages.success(
            request, f"Capo Reparto aggiornato: {nuovo_crp.cognome} {nuovo_crp.nome}{nota}."
        )
        return redirect("diaries:detail", pk=pk)


# ---------------------------------------------------------------------------
# Cambio Capo Reparto (bulk per reparto)
# ---------------------------------------------------------------------------


class CambiaCrpRepartoView(LoginRequiredMixin, View):
    """Admin/Segreteria/IABR: sostituisce il Capo Reparto per tutti i diari non ancora
    inviati di un reparto (stati prima dell'invio allo staff).
    """

    template_name = "diaries/cambia_crp_reparto.html"

    def _verifica_permessi(self, user) -> None:
        if not permessi.puo_cambiare_crp_reparto(user):
            raise PermissionDenied

    def _get_reparto_e_diari(self, reparto_pk):
        from apps.org.models import Reparto

        reparto = get_object_or_404(Reparto, pk=reparto_pk)
        return reparto, diari_service.diari_cambio_crp_reparto(reparto)

    def get(self, request, reparto_pk):
        from django.shortcuts import render

        self._verifica_permessi(request.user)
        reparto, diari = self._get_reparto_e_diari(reparto_pk)
        return render(request, self.template_name, {"reparto": reparto, "diari": diari})

    def post(self, request, reparto_pk):
        from django.core.exceptions import ValidationError
        from django.shortcuts import render

        self._verifica_permessi(request.user)
        reparto, diari = self._get_reparto_e_diari(reparto_pk)
        try:
            nuovo_crp, n = diari_service.cambia_crp_reparto(
                reparto, request.POST.get("socio_pk", "").strip(), request.user,
            )
        except ValidationError as exc:
            messages.error(request, _primo_errore(exc))
            return render(request, self.template_name, {"reparto": reparto, "diari": diari})
        messages.success(
            request,
            f"Capo Reparto aggiornato a {nuovo_crp.cognome} {nuovo_crp.nome} per {n} "
            + ("diario." if n == 1 else "diari."),
        )
        return redirect("diaries:list")
