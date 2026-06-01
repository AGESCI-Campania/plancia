# apps/siteconfig/views.py
"""Vista dedicata Impostazioni fuori dall'admin (Admin/IABR/Segreteria)."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import UpdateView

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.notifications.models import MailTemplate, TAG_REGISTRY
from apps.siteconfig.forms import ImpostazioniForm, MailTemplateForm
from apps.siteconfig.models import Impostazioni


class ImpostazioniView(RuoloRequiredMixin, UpdateView):
    """Pagina impostazioni piattaforma accessibile da Admin, IABR e Segreteria."""

    model = Impostazioni
    form_class = ImpostazioniForm
    template_name = "siteconfig/impostazioni.html"
    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def get_object(self, queryset=None):
        return Impostazioni.get()

    def form_valid(self, form):
        messages.success(self.request, "Impostazioni salvate.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Edizioni disponibili per il form import squadriglie
        from apps.editions.models import Edizione
        ctx["edizioni_import"] = Edizione.objects.order_by("-anno")
        # Mappa chiave → oggetto DB (o None) per mostrare lo stato di ogni template
        db_map = {t.chiave: t for t in MailTemplate.objects.all()}
        ctx["mail_template_righe"] = [
            {
                "chiave": chiave,
                "tag": TAG_REGISTRY.get(chiave, []),
                "template": db_map.get(chiave),
            }
            for chiave in TAG_REGISTRY
        ]
        return ctx


class LanciaImportView(RuoloRequiredMixin, View):
    """Riceve il file CSV caricato dall'utente, lo salva su disco e accodail task Celery."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)
    TRACCIATI_VALIDI = {"coca", "ragazzi", "squadriglie"}

    def post(self, request, tracciato):
        if tracciato not in self.TRACCIATI_VALIDI:
            messages.error(request, "Tracciato non valido.")
            return redirect("siteconfig:impostazioni")

        file_obj = request.FILES.get("file")
        if not file_obj:
            messages.error(request, "Seleziona un file CSV prima di avviare l'import.")
            return redirect("siteconfig:impostazioni")

        # Salva il file in MEDIA_ROOT/imports/tmp/ rendendolo accessibile al worker Celery
        import os
        from django.conf import settings
        from django.utils.text import get_valid_filename
        import time

        tmp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        nome_sicuro = get_valid_filename(file_obj.name)
        path = os.path.join(tmp_dir, f"{int(time.time())}_{nome_sicuro}")
        with open(path, "wb") as f:
            for chunk in file_obj.chunks():
                f.write(chunk)

        edizione_pk = None
        if tracciato == "squadriglie":
            try:
                edizione_pk = int(request.POST.get("edizione_pk", ""))
            except (ValueError, TypeError):
                messages.error(request, "Seleziona un'edizione per l'import squadriglie iscritte.")
                return redirect("siteconfig:impostazioni")

        from apps.imports.tasks import task_lancia_import
        task_lancia_import.delay(tracciato, path=path, edizione_pk=edizione_pk)

        label = {"coca": "Capi (Co.Ca.)", "ragazzi": "Ragazzi", "squadriglie": "Squadriglie iscritte"}
        messages.success(request, f"Import «{label[tracciato]}» avviato. Controlla lo storico per l'esito.")
        return redirect("siteconfig:impostazioni")


class MailTemplateEditView(RuoloRequiredMixin, View):
    """Crea o modifica un MailTemplate direttamente dalle impostazioni."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)
    template_name = "siteconfig/mail_template_edit.html"

    def _get_instance_and_chiave(self, chiave):
        if chiave not in TAG_REGISTRY:
            return None, None
        instance = MailTemplate.objects.filter(chiave=chiave).first()
        return instance, chiave

    def get(self, request, chiave):
        instance, chiave = self._get_instance_and_chiave(chiave)
        if chiave is None:
            messages.error(request, "Chiave template non valida.")
            return redirect("siteconfig:impostazioni")
        form = MailTemplateForm(instance=instance, chiave_fissa=chiave)
        if instance is None:
            form.initial["chiave"] = chiave
        return render(request, self.template_name, self._ctx(form, chiave, instance))

    def post(self, request, chiave):
        instance, chiave = self._get_instance_and_chiave(chiave)
        if chiave is None:
            messages.error(request, "Chiave template non valida.")
            return redirect("siteconfig:impostazioni")
        form = MailTemplateForm(request.POST, instance=instance, chiave_fissa=chiave)
        if form.is_valid():
            form.save()
            messages.success(request, f"Template «{chiave}» salvato.")
            return redirect("siteconfig:impostazioni")
        return render(request, self.template_name, self._ctx(form, chiave, instance))

    def _ctx(self, form, chiave, instance):
        tags = TAG_REGISTRY.get(chiave, [])
        return {
            "form": form,
            "chiave": chiave,
            "tag_disponibili": [{"nome": t, "tpl": "{{ " + t + " }}"} for t in tags],
            "instance": instance,
        }


class MailTemplateImportaView(RuoloRequiredMixin, View):
    """Importa il corpo HTML dal file di default in templates/mail/ e apre l'editor."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request, chiave):
        if chiave not in TAG_REGISTRY:
            messages.error(request, "Chiave template non valida.")
            return redirect("siteconfig:impostazioni")
        if MailTemplate.objects.filter(chiave=chiave).exists():
            messages.warning(request, f"Il template «{chiave}» esiste già — modifica quello.")
            return redirect("siteconfig:mail_template_edit", chiave=chiave)

        from django.template.loader import get_template
        from django.template import TemplateDoesNotExist
        try:
            tpl = get_template(f"mail/{chiave}.html")
            corpo = tpl.template.source
        except TemplateDoesNotExist:
            corpo = ""
            messages.warning(request, f"File mail/{chiave}.html non trovato: template creato vuoto.")

        MailTemplate.objects.create(
            chiave=chiave,
            oggetto=chiave.replace("_", " ").capitalize(),
            corpo_html=corpo,
            attivo=True,
        )
        messages.success(request, f"Template «{chiave}» importato dal file di default.")
        return redirect("siteconfig:mail_template_edit", chiave=chiave)


class MailTemplateDeleteView(RuoloRequiredMixin, View):
    """Elimina un MailTemplate (ripristina il fallback su file)."""

    ruoli_ammessi = (Ruolo.ADMIN,)

    def post(self, request, chiave):
        tpl = get_object_or_404(MailTemplate, chiave=chiave)
        tpl.delete()
        messages.success(request, f"Template «{chiave}» eliminato — verrà usato il file di default.")
        return redirect("siteconfig:impostazioni")
