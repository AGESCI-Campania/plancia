# apps/diaries/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView, UpdateView, View

from apps.accounts.models import Ruolo
from apps.diaries.forms import (
    AnagraficaForm,
    BrevettoFormSet,
    ImpresaForm,
    MembroSqFormSet,
    MissioneForm,
    PostoAzioneFormSet,
    PostoAzioneMissioneFormSet,
    PresentazioneForm,
    RelazioneFinaleForm,
    SpecialitaFormSet,
)
from apps.diaries.models import (
    Allegato,
    Anagrafica,
    Diario,
    Impresa,
    MODULI_FOTO,
    Missione,
    Presentazione,
    RelazioneFinale,
    StatoDiario,
    StatoSync,
    TipoDiario,
    TipoEsito,
)


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
        user = self.request.user
        if user.is_superuser or user.is_staff_plancia:
            return diario
        if user.ruolo == Ruolo.CSQ and user.socio and diario.csq == user.socio:
            return diario
        if user.ruolo == Ruolo.CRP and user.socio and diario.crp == user.socio:
            return diario
        if user.ruolo == Ruolo.PGV:
            # La verifica delle assegnazioni avviene nel modulo evaluations (futuro)
            return diario
        raise PermissionDenied

    def _puo_editare(self, diario: Diario) -> bool:
        """True se l'utente può editare il contenuto del diario."""
        user = self.request.user
        if user.is_superuser or user.is_staff_plancia:
            return True
        return (
            diario.stato == StatoDiario.IN_COMPILAZIONE
            and user.ruolo in (Ruolo.CSQ, Ruolo.CRP)
        )


# ---------------------------------------------------------------------------
# Lista e dettaglio
# ---------------------------------------------------------------------------

class DiarioListView(LoginRequiredMixin, ListView):
    template_name = "diaries/list.html"
    context_object_name = "diari"

    def get_queryset(self):
        user = self.request.user
        qs = Diario.objects.select_related("edizione", "squadriglia", "csq", "crp")
        if user.is_superuser or user.is_staff_plancia:
            return qs
        if user.ruolo == Ruolo.CSQ and user.socio:
            return qs.filter(csq=user.socio)
        if user.ruolo == Ruolo.CRP and user.socio:
            return qs.filter(crp=user.socio)
        if user.ruolo == Ruolo.PGV:
            # PGV vede solo i diari a lui assegnati tramite AssegnazionePGV
            from apps.evaluations.models import AssegnazionePGV
            assegnati = AssegnazionePGV.objects.filter(pgv=user).values_list("valutazione__diario_id", flat=True)
            return qs.filter(pk__in=assegnati)
        return qs.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.editions.models import Edizione
        ctx["edizioni"] = Edizione.objects.all()
        edizione_pk = self.request.GET.get("edizione")
        if edizione_pk:
            ctx["diari"] = ctx["diari"].filter(edizione_id=edizione_pk)
            ctx["edizione_sel"] = edizione_pk
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
        user = self.request.user
        is_csq = user.ruolo == Ruolo.CSQ
        ctx["puo_editare"] = self._puo_editare(diario)
        ctx["is_csq"] = is_csq
        # Relazione finale: mai visibile al CSQ (docs sez. 5)
        ctx["mostra_relazione"] = not is_csq
        # Completezza moduli CSQ
        ctx["moduli_csq_completi"] = diario.moduli_csq_completi
        # Moduli esistenti
        ctx["has_anagrafica"] = hasattr(diario, "anagrafica")
        ctx["has_presentazione"] = hasattr(diario, "presentazione")
        ctx["imprese"] = diario.imprese.all()
        ctx["has_imp2"] = diario.imprese.filter(numero=2).exists()
        ctx["has_missione"] = hasattr(diario, "missione")
        ctx["has_relazione"] = hasattr(diario, "relazione_finale")
        ctx["puo_inviare"] = (
            diario.stato == StatoDiario.IN_COMPILAZIONE
            and diario.moduli_csq_completi
            and user.ruolo in (Ruolo.CSQ, Ruolo.CRP)
        )
        ctx["puo_riapire"] = diario.puo_essere_riaperto() and user.is_staff_plancia
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
        diario, anagrafica = self._setup(pk)
        form = AnagraficaForm(instance=anagrafica, utente=request.user)
        return render(request, self.template_name, {"form": form, "diario": diario})

    def post(self, request, pk):
        from django.shortcuts import render
        diario, anagrafica = self._setup(pk)
        form = AnagraficaForm(request.POST, instance=anagrafica, utente=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Anagrafica salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "diario": diario})


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
        return render(request, self.template_name, {
            "form": form, "formset": formset, "diario": diario
        })

    def post(self, request, pk):
        from django.shortcuts import render
        diario, presentazione = self._setup(pk)
        form = PresentazioneForm(request.POST, instance=presentazione)
        formset = MembroSqFormSet(request.POST, instance=presentazione)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Presentazione salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name, {
            "form": form, "formset": formset, "diario": diario
        })


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
        return render(request, self.template_name, {
            "form": form, "posti_fs": posti_fs,
            "specialita_fs": specialita_fs, "brevetti_fs": brevetti_fs,
            "diario": diario, "numero": numero,
        })

    def post(self, request, pk, numero):
        from django.shortcuts import render
        diario, impresa = self._setup(pk, numero)
        form = ImpresaForm(request.POST, instance=impresa)
        posti_fs = PostoAzioneFormSet(request.POST, instance=impresa, prefix="posti")
        specialita_fs = SpecialitaFormSet(
            request.POST, instance=impresa,
            queryset=impresa.esiti_specialita.filter(tipo=TipoEsito.SPECIALITA),
            prefix="specialita",
        )
        brevetti_fs = BrevettoFormSet(
            request.POST, instance=impresa,
            queryset=impresa.esiti_specialita.filter(tipo=TipoEsito.BREVETTO),
            prefix="brevetti",
        )
        if form.is_valid() and posti_fs.is_valid() and specialita_fs.is_valid() and brevetti_fs.is_valid():
            form.save()
            posti_fs.save()
            specialita_fs.save()
            brevetti_fs.save()
            messages.success(request, f"{numero}ª impresa salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name, {
            "form": form, "posti_fs": posti_fs,
            "specialita_fs": specialita_fs, "brevetti_fs": brevetti_fs,
            "diario": diario, "numero": numero,
        })


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

    def get(self, request, pk):
        from django.shortcuts import render
        diario, missione = self._setup(pk)
        form = MissioneForm(instance=missione)
        posti_fs = PostoAzioneMissioneFormSet(instance=missione)
        return render(request, self.template_name, {
            "form": form, "posti_fs": posti_fs, "diario": diario
        })

    def post(self, request, pk):
        from django.shortcuts import render
        diario, missione = self._setup(pk)
        form = MissioneForm(request.POST, instance=missione)
        posti_fs = PostoAzioneMissioneFormSet(request.POST, instance=missione)
        if form.is_valid() and posti_fs.is_valid():
            form.save()
            posti_fs.save()
            messages.success(request, "Missione salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name, {
            "form": form, "posti_fs": posti_fs, "diario": diario
        })


# ---------------------------------------------------------------------------
# Modulo 6 — Relazione finale CRP
# ---------------------------------------------------------------------------

class RelazioneFinaleUpdateView(DiarioAccessMixin, View):
    template_name = "diaries/modules/relazione.html"

    def _setup(self, pk):
        diario = self._get_diario(pk)
        user = self.request.user
        # Solo CRP/staff, mai CSQ (docs sez. 5)
        if user.ruolo == Ruolo.CSQ and not user.is_superuser:
            raise PermissionDenied
        if not self._puo_editare(diario):
            raise PermissionDenied
        # Compilabile solo dopo che i moduli CSQ obbligatori sono completi
        if not diario.moduli_csq_completi and not user.is_superuser:
            messages.warning(self.request, "La relazione CRP è disponibile dopo il completamento dei moduli CSQ.")
            return redirect("diaries:detail", pk=pk), None, None
        relazione, _ = RelazioneFinale.objects.get_or_create(diario=diario)
        return diario, relazione, None

    def get(self, request, pk):
        from django.shortcuts import render
        result = self._setup(pk)
        if isinstance(result[0], type(redirect("/").__class__)):
            return result[0]
        diario, relazione, _ = result
        form = RelazioneFinaleForm(instance=relazione)
        return render(request, self.template_name, {"form": form, "diario": diario})

    def post(self, request, pk):
        from django.shortcuts import render
        diario = self._get_diario(pk)
        user = request.user
        if user.ruolo == Ruolo.CSQ and not user.is_superuser:
            raise PermissionDenied
        if not self._puo_editare(diario):
            raise PermissionDenied
        relazione, _ = RelazioneFinale.objects.get_or_create(diario=diario)
        form = RelazioneFinaleForm(request.POST, instance=relazione)
        if form.is_valid():
            form.save()
            messages.success(request, "Relazione finale salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "diario": diario})


# ---------------------------------------------------------------------------
# Transizioni FSM
# ---------------------------------------------------------------------------

class DiarioInviaView(DiarioAccessMixin, View):
    """IN_COMPILAZIONE → INVIATO."""

    def post(self, request, pk):
        diario = self._get_diario(pk)
        user = request.user
        if user.ruolo not in (Ruolo.CSQ, Ruolo.CRP) and not user.is_superuser:
            raise PermissionDenied
        try:
            diario.invia()
            messages.success(request, "Diario inviato con successo.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("diaries:detail", pk=pk)


class DiarioRiapriView(DiarioAccessMixin, View):
    """NON_APPROVATO / MAGGIORI_INFO → IN_COMPILAZIONE (staff only)."""

    def post(self, request, pk):
        diario = self._get_diario(pk)
        if not request.user.is_staff_plancia and not request.user.is_superuser:
            raise PermissionDenied
        try:
            diario.riapri()
            messages.success(request, "Diario riaperto per integrazioni.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("diaries:detail", pk=pk)


# ---------------------------------------------------------------------------
# Allegati (foto)
# ---------------------------------------------------------------------------

_MIME_CONSENTITI = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
_MAX_BYTES = 20 * 1024 * 1024  # 20 MB


def _allegato_json(a: Allegato) -> dict:
    return {
        "id": a.pk,
        "nome": a.nome,
        "mime": a.mime,
        "dimensione": a.dimensione,
        "stato_sync": a.stato_sync,
        "url": a.file.url if a.file else None,
    }


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
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            return JsonResponse({"error": "Non autorizzato"}, status=403)

        modulo = request.POST.get("modulo", "")
        if modulo not in MODULI_FOTO:
            return JsonResponse({"error": "Modulo non valido"}, status=400)

        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"error": "Nessun file"}, status=400)

        if file.content_type not in _MIME_CONSENTITI:
            return JsonResponse({"error": f"Tipo non consentito: {file.content_type}"}, status=400)
        if file.size > _MAX_BYTES:
            return JsonResponse({"error": "File troppo grande (max 20 MB)"}, status=400)

        allegato = Allegato.objects.create(
            diario=diario,
            modulo=modulo,
            nome=file.name,
            mime=file.content_type,
            dimensione=file.size,
            file=file,
            caricato_da=request.user,
            stato_sync=StatoSync.LOCALE,
        )
        return JsonResponse(_allegato_json(allegato), status=201)


class AllegatoDeleteView(DiarioAccessMixin, View):
    """POST /diari/<pk>/allegati/<allegato_pk>/elimina/  →  {ok: true}"""

    def post(self, request, pk, allegato_pk):
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            return JsonResponse({"error": "Non autorizzato"}, status=403)
        allegato = get_object_or_404(Allegato, pk=allegato_pk, diario=diario)
        if allegato.file:
            allegato.file.delete(save=False)
        allegato.delete()
        return JsonResponse({"ok": True})
