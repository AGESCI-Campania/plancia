# apps/siteconfig/views.py
"""Vista dedicata Impostazioni fuori dall'admin (Admin/IABR/Segreteria)."""
from __future__ import annotations

import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import UpdateView

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.notifications.models import TAG_REGISTRY, MailTemplate
from apps.siteconfig.forms import FooterLinkFormSet, ImpostazioniForm, MailTemplateForm
from apps.siteconfig.models import Impostazioni


class ImpostazioniView(RuoloRequiredMixin, UpdateView):
    """Pagina impostazioni piattaforma accessibile da Admin, IABR e Segreteria."""

    model = Impostazioni
    form_class = ImpostazioniForm
    template_name = "siteconfig/impostazioni.html"
    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def get_object(self, queryset=None):
        return Impostazioni.get()

    def get_success_url(self):
        return self.request.path

    def get_context_data(self, **kwargs):
        if "link_formset" not in kwargs:
            kwargs["link_formset"] = FooterLinkFormSet(instance=self.get_object())
        ctx = super().get_context_data(**kwargs)
        from apps.editions.models import Edizione
        ctx["edizioni_import"] = Edizione.objects.order_by("-anno")
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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        link_formset = FooterLinkFormSet(request.POST, instance=self.object)
        if form.is_valid() and link_formset.is_valid():
            form.save()
            link_formset.save()
            messages.success(request, "Impostazioni salvate.")
            return redirect(self.get_success_url())
        return self.render_to_response(
            self.get_context_data(form=form, link_formset=link_formset)
        )


class LanciaImportView(RuoloRequiredMixin, View):
    """Riceve il file CSV caricato dall'utente, lo salva su disco e accodail task Celery."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)
    TRACCIATI_VALIDI = {"coca", "ragazzi", "squadriglie"}

    def post(self, request, tracciato):
        if tracciato not in self.TRACCIATI_VALIDI:
            messages.error(request, "Tracciato non valido.")
            return redirect("imports:log_list")

        file_obj = request.FILES.get("file")
        if not file_obj:
            messages.error(request, "Seleziona un file CSV prima di avviare l'import.")
            return redirect("imports:log_list")

        # Salva il file in MEDIA_ROOT/imports/tmp/ rendendolo accessibile al worker Celery
        import os
        import time

        from django.conf import settings
        from django.utils.text import get_valid_filename

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
                return redirect("imports:log_list")

        from apps.imports.tasks import task_lancia_import
        task_lancia_import.delay(tracciato, path=path, edizione_pk=edizione_pk)

        label = {"coca": "Capi (Co.Ca.)", "ragazzi": "Ragazzi", "squadriglie": "Squadriglie iscritte"}
        messages.success(request, f"Import «{label[tracciato]}» avviato. Controlla lo storico per l'esito.")
        return redirect("imports:log_list")


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
        db_keys = set(MailTemplate.objects.values_list("chiave", flat=True))
        chiavi_senza_record = [k for k in TAG_REGISTRY if k != chiave and k not in db_keys]
        return {
            "form": form,
            "chiave": chiave,
            "tag_disponibili": [{"nome": t, "tpl": "{{ " + t + " }}"} for t in tags],
            "instance": instance,
            "chiavi_senza_record": chiavi_senza_record,
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

        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template
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


class MailTemplateCopiaView(RuoloRequiredMixin, View):
    """Duplica oggetto e corpo_html di un MailTemplate verso una nuova chiave senza record DB."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request, chiave):
        source = get_object_or_404(MailTemplate, chiave=chiave)
        target_chiave = request.POST.get("target_chiave", "").strip()
        if target_chiave not in TAG_REGISTRY:
            messages.error(request, "Chiave target non valida.")
            return redirect("siteconfig:mail_template_edit", chiave=chiave)
        if MailTemplate.objects.filter(chiave=target_chiave).exists():
            messages.warning(request, f"Il template «{target_chiave}» esiste già.")
            return redirect("siteconfig:mail_template_edit", chiave=target_chiave)
        MailTemplate.objects.create(
            chiave=target_chiave,
            oggetto=source.oggetto,
            corpo_html=source.corpo_html,
            attivo=source.attivo,
        )
        messages.success(request, f"Template «{target_chiave}» creato da «{chiave}».")
        return redirect("siteconfig:mail_template_edit", chiave=target_chiave)


@method_decorator(csrf_exempt, name="dispatch")
class MailTemplateImageUploadView(RuoloRequiredMixin, View):
    """Endpoint upload immagini per TinyMCE nei template email."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)
    _ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
    _MAX_SIZE = 2 * 1024 * 1024  # 2 MB

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return JsonResponse({"error": "Nessun file ricevuto."}, status=400)
        if upload.content_type not in self._ALLOWED_TYPES:
            return JsonResponse(
                {"error": "Tipo non supportato. Usa JPEG, PNG, GIF o WebP."}, status=400
            )
        if upload.size > self._MAX_SIZE:
            return JsonResponse({"error": "File troppo grande (max 2 MB)."}, status=400)

        ext = os.path.splitext(upload.name)[1].lower() or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        save_dir = os.path.join(settings.MEDIA_ROOT, "mail_images")
        os.makedirs(save_dir, exist_ok=True)

        with open(os.path.join(save_dir, filename), "wb") as fh:
            for chunk in upload.chunks():
                fh.write(chunk)

        media_prefix = "/" + settings.MEDIA_URL.lstrip("/")
        location = request.build_absolute_uri(f"{media_prefix}mail_images/{filename}")
        return JsonResponse({"location": location})


class MailTemplateDeleteView(RuoloRequiredMixin, View):
    """Elimina un MailTemplate (ripristina il fallback su file)."""

    ruoli_ammessi = (Ruolo.ADMIN,)

    def post(self, request, chiave):
        tpl = get_object_or_404(MailTemplate, chiave=chiave)
        tpl.delete()
        messages.success(request, f"Template «{chiave}» eliminato — verrà usato il file di default.")
        return redirect("siteconfig:impostazioni")


class MailpitProxyView(View):
    """Proxy verso Mailpit per il debug delle email in produzione.

    Accessibile su /mailadmin/ solo per utenti staff. Richiede che Mailpit sia
    avviato con --ui-web-path /mailadmin e raggiungibile all'URL MAILPIT_INTERNAL_URL.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_staff_plancia or request.user.is_superuser):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Accesso riservato agli amministratori.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, path=""):
        return self._proxy(request, path)

    def post(self, request, path=""):
        return self._proxy(request, path)

    def delete(self, request, path=""):
        return self._proxy(request, path)

    def _proxy(self, request, path):
        import urllib.error
        import urllib.request
        from urllib.parse import urlencode

        from django.http import HttpResponse

        mailpit_base = getattr(settings, "MAILPIT_INTERNAL_URL", "http://mailpit:8025").rstrip("/")
        target_path = f"/mailadmin/{path}".rstrip("/") or "/mailadmin/"
        target_url = mailpit_base + target_path
        if request.GET:
            target_url += "?" + urlencode(request.GET)

        headers = {}
        for name in ("Content-Type", "Accept", "X-Requested-With"):
            if name in request.headers:
                headers[name] = request.headers[name]

        body = request.body if request.method in ("POST", "PUT", "PATCH") else None
        req = urllib.request.Request(target_url, data=body, headers=headers, method=request.method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
                content_type = resp.headers.get("Content-Type", "text/html")
                return HttpResponse(content, status=resp.status, content_type=content_type)
        except urllib.error.HTTPError as e:
            return HttpResponse(e.read(), status=e.code)
        except Exception as e:
            return HttpResponse(
                f"<h1>Mailpit non raggiungibile</h1><pre>{e}</pre>"
                "<p>Avvia Mailpit con il profilo <code>mailpit</code>: "
                "<code>COMPOSE_PROFILES=proxy-nginx,mailpit docker compose up -d</code></p>",
                status=503,
                content_type="text/html",
            )
