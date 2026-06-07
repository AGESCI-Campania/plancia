# apps/diaries/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView, View

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
    MODULI_FOTO,
    Allegato,
    Anagrafica,
    Diario,
    Impresa,
    Missione,
    Presentazione,
    RelazioneFinale,
    StatoDiario,
    StatoSync,
    TipoDiario,
    TipoEsito,
)

# Stati in cui il diario non è ancora stato inviato allo staff
_STATI_PRIMA_INVIO = (StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE, StatoDiario.RELAZIONE_FINALE)

# Stati in cui ha senso generare il PDF (CSQ ha inviato la propria parte)
_STATI_PDF = (
    StatoDiario.INVIATO, StatoDiario.IN_VALUTAZIONE, StatoDiario.IN_REVISIONE,
    StatoDiario.APPROVATO, StatoDiario.NON_APPROVATO, StatoDiario.MAGGIORI_INFO,
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
        """True se l'utente può editare i moduli CSQ (1-5) del diario."""
        user = self.request.user
        if user.is_superuser or user.is_staff_plancia:
            return True
        return diario.stato in (StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE) and user.ruolo == Ruolo.CSQ

    def _inizia_se_necessario(self, diario: Diario) -> None:
        """Transita NON_INIZIATO → IN_COMPILAZIONE al primo salvataggio del CSQ."""
        if diario.stato == StatoDiario.NON_INIZIATO:
            diario.inizia()

    def _puo_editare_relazione(self, diario: Diario) -> bool:
        """True se il Capo Reparto può compilare la relazione finale (modulo 6)."""
        user = self.request.user
        if user.is_superuser or user.is_staff_plancia:
            return True
        return diario.stato == StatoDiario.RELAZIONE_FINALE and user.ruolo == Ruolo.CRP


# ---------------------------------------------------------------------------
# Lista e dettaglio
# ---------------------------------------------------------------------------


class DiarioListView(LoginRequiredMixin, ListView):
    template_name = "diaries/list.html"
    context_object_name = "diari"

    def get_queryset(self):
        user = self.request.user
        qs = Diario.objects.select_related(
            "edizione",
            "squadriglia__reparto__gruppo__zona",
            "csq", "crp", "anagrafica",
        )
        if user.is_superuser or user.is_staff_plancia:
            return qs
        if user.ruolo == Ruolo.CSQ and user.socio:
            return qs.filter(csq=user.socio)
        if user.ruolo == Ruolo.CRP and user.socio:
            return qs.filter(crp=user.socio)
        if user.ruolo == Ruolo.PGV:
            # PGV vede solo i diari a lui assegnati tramite AssegnazionePGV
            from apps.evaluations.models import AssegnazionePGV

            assegnati = AssegnazionePGV.objects.filter(pgv=user).values_list(
                "valutazione__diario_id", flat=True
            )
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
        # Capo Squadriglia può inviare la propria parte (→ Relazione finale)
        ctx["puo_inviare_csq"] = (
            diario.stato == StatoDiario.IN_COMPILAZIONE
            and diario.moduli_csq_completi
            and (user.ruolo == Ruolo.CSQ or user.is_superuser or user.is_staff_plancia)
        )
        # Capo Reparto può inviare il diario allo staff (→ Inviato)
        ctx["puo_inviare"] = diario.stato == StatoDiario.RELAZIONE_FINALE and (
            user.ruolo == Ruolo.CRP or user.is_superuser or user.is_staff_plancia
        )
        ctx["puo_riapire"] = diario.puo_essere_riaperto() and user.is_staff_plancia
        # Cambio CSQ: CRP quando NON_INIZIATO/IN_COMPILAZIONE; admin/seg/iabr prima dell'invio
        ctx["puo_cambiare_csq"] = (
            diario.stato in (StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE)
            and user.ruolo == Ruolo.CRP
            and user.socio is not None
            and diario.crp == user.socio
        ) or ((user.is_superuser or user.is_staff_plancia) and diario.stato in _STATI_PRIMA_INVIO)
        # Cambio CRP: solo admin/seg/iabr prima dell'invio
        ctx["puo_cambiare_crp"] = (
            user.is_superuser or user.is_staff_plancia
        ) and diario.stato in _STATI_PRIMA_INVIO
        # Dilazione (solo staff)
        if user.is_staff_plancia or user.is_superuser:
            from apps.editions.forms import DilazioneForm
            ctx["dilazione_form"] = DilazioneForm()
        ctx["puo_pdf"] = diario.stato in _STATI_PDF
        # Allegati per modulo (conteggio + anteprime foto nel detail)
        allegati_all = list(diario.allegati.all())
        ctx["allegati_impresa_1"] = [a for a in allegati_all if a.modulo == "impresa_1"]
        ctx["allegati_impresa_2"] = [a for a in allegati_all if a.modulo == "impresa_2"]
        ctx["allegati_missione"] = [a for a in allegati_all if a.modulo == "missione"]
        ctx["puo_editare_relazione"] = self._puo_editare_relazione(diario)
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
        self._inizia_se_necessario(diario)
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
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "posti_fs": posti_fs,
                "specialita_fs": specialita_fs,
                "brevetti_fs": brevetti_fs,
                "diario": diario,
                "numero": numero,
            },
        )

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
            messages.success(request, f"{numero}ª impresa salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "posti_fs": posti_fs,
                "specialita_fs": specialita_fs,
                "brevetti_fs": brevetti_fs,
                "diario": diario,
                "numero": numero,
            },
        )


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
        return render(
            request, self.template_name, {"form": form, "posti_fs": posti_fs, "diario": diario}
        )

    def post(self, request, pk):
        from django.shortcuts import render

        diario, missione = self._setup(pk)
        self._inizia_se_necessario(diario)
        form = MissioneForm(request.POST, instance=missione)
        posti_fs = PostoAzioneMissioneFormSet(request.POST, instance=missione)
        if form.is_valid() and posti_fs.is_valid():
            form.save()
            posti_fs.save()
            messages.success(request, "Missione salvata.")
            return redirect("diaries:detail", pk=pk)
        return render(
            request, self.template_name, {"form": form, "posti_fs": posti_fs, "diario": diario}
        )


# ---------------------------------------------------------------------------
# Modulo 6 — Relazione finale CRP
# ---------------------------------------------------------------------------


class RelazioneFinaleUpdateView(DiarioAccessMixin, View):
    template_name = "diaries/modules/relazione.html"

    def _check_permessi(self, diario, user):
        """Verifica accesso e precondizioni; lancia PermissionDenied o redirect se non ok."""
        if user.ruolo == Ruolo.CSQ and not user.is_superuser:
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
        diario = self._get_diario(pk)
        user = request.user
        try:
            if diario.stato == StatoDiario.IN_COMPILAZIONE:
                if user.ruolo != Ruolo.CSQ and not user.is_superuser and not user.is_staff_plancia:
                    raise PermissionDenied
                diario.csq_invia()
                messages.success(
                    request,
                    "Parte del Capo Squadriglia inviata. Il Capo Reparto può ora compilare la relazione finale.",
                )
            elif diario.stato == StatoDiario.RELAZIONE_FINALE:
                if user.ruolo != Ruolo.CRP and not user.is_superuser and not user.is_staff_plancia:
                    raise PermissionDenied
                diario.invia()
                messages.success(request, "Diario inviato allo staff.")
            else:
                messages.error(request, "Invio non consentito nello stato attuale.")
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


class DiarioPdfView(DiarioAccessMixin, View):
    """GET /diari/<pk>/pdf/ — serve il PDF dalla cache Drive o avvia la generazione async."""

    def get(self, request, pk):
        import io

        diario = self._get_diario(pk)

        # 1. Controlla se esiste già un PDF in cache (DriveFile tipo=PDF)
        from apps.storage_drive.models import DriveFile, TipoFile
        cache = DriveFile.objects.filter(diario=diario, tipo=TipoFile.PDF).first()
        if cache and cache.drive_file_id:
            try:
                from googleapiclient.http import MediaIoBaseDownload

                from apps.storage_drive.service import _build_drive_service, _get_credenziali
                cred = _get_credenziali(diario.edizione)
                service = _build_drive_service(cred)
                req = service.files().get_media(fileId=cache.drive_file_id)
                buf = io.BytesIO()
                dl = MediaIoBaseDownload(buf, req, chunksize=4 * 1024 * 1024)
                done = False
                while not done:
                    _, done = dl.next_chunk()
                buf.seek(0)
                content = buf.read()
                nome = cache.nome or f"Diario_{diario.squadriglia.nome}_{diario.edizione.anno}.pdf"
                response = HttpResponse(content, content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="{nome}"'
                response["Content-Length"] = len(content)
                return response
            except Exception:
                # Cache corrotta o file rimosso da Drive: rigenera
                cache.delete()

        # 2. Se Drive non configurato: genera sincrono (senza foto, veloce)
        if not diario.edizione.drive_oauth_account:
            try:
                from apps.exports.service import genera_pdf_diario
                pdf = genera_pdf_diario(diario)
                nome = f"Diario_{diario.squadriglia.nome}_{diario.edizione.anno}.pdf"
                response = HttpResponse(pdf, content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="{nome}"'
                response["Content-Length"] = len(pdf)
                return response
            except Exception as exc:
                messages.error(request, f"Errore nella generazione del PDF: {exc}")
                return redirect("diaries:detail", pk=pk)

        # 3. Drive configurato ma nessuna cache: avvia task Celery asincrono
        from apps.exports.tasks import _invia_mail_pdf, task_genera_pdf_diario
        _invia_mail_pdf("diario_pdf_in_generazione", request.user.pk, diario)
        task_genera_pdf_diario.delay(diario.pk, request.user.pk)
        messages.info(
            request,
            "Il PDF è in fase di generazione. "
            f"Riceverai una mail all'indirizzo {request.user.email} quando sarà pronto.",
        )
        return redirect("diaries:detail", pk=pk)


class AllegatoPreviewView(DiarioAccessMixin, View):
    """GET /diari/<pk>/allegati/<allegato_pk>/preview/ → immagine dal Drive (proxy)."""

    def get(self, request, pk, allegato_pk):
        import io

        diario = self._get_diario(pk)
        allegato = get_object_or_404(Allegato, pk=allegato_pk, diario=diario)

        if not allegato.drive_file_id or not allegato.mime.startswith("image/"):
            raise Http404

        try:
            from googleapiclient.http import MediaIoBaseDownload

            from apps.storage_drive.service import _build_drive_service, _get_credenziali

            cred = _get_credenziali(diario.edizione)
            service = _build_drive_service(cred)
            req = service.files().get_media(fileId=allegato.drive_file_id)
            buf = io.BytesIO()
            dl = MediaIoBaseDownload(buf, req, chunksize=4 * 1024 * 1024)
            done = False
            while not done:
                _, done = dl.next_chunk()
            buf.seek(0)
            response = HttpResponse(buf.read(), content_type=allegato.mime)
            response["Cache-Control"] = "private, max-age=86400"
            return response
        except Exception:
            raise Http404 from None


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
        self._inizia_se_necessario(diario)

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

        drive_configurato = bool(diario.edizione.drive_oauth_account)
        allegato = Allegato.objects.create(
            diario=diario,
            modulo=modulo,
            nome=file.name,
            mime=file.content_type,
            dimensione=file.size,
            file=file,
            caricato_da=request.user,
            stato_sync=StatoSync.IN_CODA if drive_configurato else StatoSync.LOCALE,
        )
        if drive_configurato:
            from apps.storage_drive.tasks import task_carica_allegato_drive
            task_carica_allegato_drive.delay(allegato.pk)
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


# ---------------------------------------------------------------------------
# Cambio Capo Squadriglia
# ---------------------------------------------------------------------------


class CambiaCsqView(DiarioAccessMixin, View):
    """Cambia il Capo Squadriglia di un diario.

    - Capo Reparto: solo quando IN_COMPILAZIONE e per i diari di cui è referente.
    - Admin/Segreteria/IABR: quando IN_COMPILAZIONE o RELAZIONE_FINALE.
    """

    template_name = "diaries/cambia_csq.html"

    def _verifica_permessi(self, diario, user) -> None:
        if user.is_superuser or user.is_staff_plancia:
            if diario.stato not in _STATI_PRIMA_INVIO:
                raise PermissionDenied
            return
        if (
            user.ruolo == Ruolo.CRP
            and user.socio is not None
            and diario.crp == user.socio
            and diario.stato == StatoDiario.IN_COMPILAZIONE
        ):
            return
        raise PermissionDenied

    def get(self, request, pk):
        from django.shortcuts import render

        diario = self._get_diario(pk)
        self._verifica_permessi(diario, request.user)
        return render(request, self.template_name, {"diario": diario})

    def post(self, request, pk):
        from django.shortcuts import render

        diario = self._get_diario(pk)
        self._verifica_permessi(diario, request.user)
        socio_pk = request.POST.get("socio_pk", "").strip()
        if not socio_pk:
            messages.error(request, "Seleziona un Capo Squadriglia.")
            return render(request, self.template_name, {"diario": diario})
        from apps.org.models import Socio

        try:
            nuovo_csq = Socio.objects.get(pk=socio_pk, categoria="ragazzo", provvisorio=False)
        except Socio.DoesNotExist, ValueError:
            messages.error(request, "Capo Squadriglia non valido.")
            return render(request, self.template_name, {"diario": diario})
        vecchio = diario.csq
        diario.csq = nuovo_csq
        diario.save(update_fields=["csq"])
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
        if not (user.is_superuser or user.is_staff_plancia):
            raise PermissionDenied
        if diario.stato not in _STATI_PRIMA_INVIO:
            raise PermissionDenied

    def get(self, request, pk):
        from django.shortcuts import render

        diario = self._get_diario(pk)
        self._verifica_permessi(diario, request.user)
        return render(request, self.template_name, {"diario": diario})

    def post(self, request, pk):
        from django.shortcuts import render

        diario = self._get_diario(pk)
        self._verifica_permessi(diario, request.user)
        socio_pk = request.POST.get("socio_pk", "").strip()
        if not socio_pk:
            messages.error(request, "Seleziona un Capo Reparto.")
            return render(request, self.template_name, {"diario": diario})
        from apps.org.models import Socio

        try:
            nuovo_crp = Socio.objects.get(pk=socio_pk, categoria="capo", provvisorio=False)
        except Socio.DoesNotExist, ValueError:
            messages.error(request, "Capo Reparto non valido.")
            return render(request, self.template_name, {"diario": diario})
        vecchio = diario.crp
        diario.crp = nuovo_crp
        diario.save(update_fields=["crp"])
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
    inviati di un reparto (stato IN_COMPILAZIONE o RELAZIONE_FINALE).
    """

    template_name = "diaries/cambia_crp_reparto.html"

    def _verifica_permessi(self, user) -> None:
        if not (user.is_superuser or user.is_staff_plancia):
            raise PermissionDenied

    def _get_reparto_e_diari(self, reparto_pk):
        from apps.org.models import Reparto

        reparto = get_object_or_404(Reparto, pk=reparto_pk)
        diari = (
            Diario.objects.filter(squadriglia__reparto=reparto, stato__in=_STATI_PRIMA_INVIO)
            .select_related("squadriglia", "csq", "crp", "edizione")
            .order_by("edizione__anno", "squadriglia__nome")
        )
        return reparto, diari

    def get(self, request, reparto_pk):
        from django.shortcuts import render

        self._verifica_permessi(request.user)
        reparto, diari = self._get_reparto_e_diari(reparto_pk)
        return render(request, self.template_name, {"reparto": reparto, "diari": diari})

    def post(self, request, reparto_pk):
        from django.shortcuts import render

        self._verifica_permessi(request.user)
        reparto, diari = self._get_reparto_e_diari(reparto_pk)
        socio_pk = request.POST.get("socio_pk", "").strip()
        if not socio_pk:
            messages.error(request, "Seleziona un Capo Reparto.")
            return render(request, self.template_name, {"reparto": reparto, "diari": diari})
        from apps.org.models import Socio

        try:
            nuovo_crp = Socio.objects.get(pk=socio_pk, categoria="capo", provvisorio=False)
        except Socio.DoesNotExist, ValueError:
            messages.error(request, "Capo Reparto non valido.")
            return render(request, self.template_name, {"reparto": reparto, "diari": diari})
        n = diari.update(crp=nuovo_crp)
        messages.success(
            request,
            f"Capo Reparto aggiornato a {nuovo_crp.cognome} {nuovo_crp.nome} per {n} "
            + ("diario." if n == 1 else "diari."),
        )
        return redirect("diaries:list")
