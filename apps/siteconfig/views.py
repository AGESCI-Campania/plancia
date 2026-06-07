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

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.notifications.models import TAG_REGISTRY, MailTemplate
from apps.siteconfig.forms import (
    CAMPI_SMTP_MANUALI,
    SEZIONE_FORM,
    SEZIONE_LABEL,
    FooterLinkFormSet,
    MailTemplateForm,
    PaginaStaticaForm,
)
from apps.siteconfig.models import Impostazioni, PaginaStatica, SlugPagina


class ImpostazioniView(RuoloRequiredMixin, View):
    """Pagina impostazioni piattaforma. Ogni sezione ha il proprio form isolato."""

    template_name = "siteconfig/impostazioni.html"
    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def _build_context(self, imp, **form_overrides):
        from axes.models import AccessAttempt

        from apps.editions.models import Edizione

        ctx: dict = {"object": imp}

        # Form per sezione — usa override se c'è un form con errori da mostrare
        for sezione, form_class in SEZIONE_FORM.items():
            key = f"form_{sezione}"
            ctx[key] = form_overrides.get(key, form_class(instance=imp))

        # Formset footer
        ctx["link_formset"] = form_overrides.get(
            "link_formset", FooterLinkFormSet(instance=imp)
        )

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
        ctx["access_attempts"] = AccessAttempt.objects.order_by("-attempt_time")[:100]
        return ctx

    def get(self, request, *args, **kwargs):
        imp = Impostazioni.objects.get_or_create(pk=1)[0]
        return render(request, self.template_name, self._build_context(imp))

    def post(self, request, *args, **kwargs):
        from django.core.cache import cache

        sezione = request.POST.get("sezione", "")
        if sezione not in SEZIONE_FORM:
            messages.error(request, "Sezione non valida.")
            return redirect("siteconfig:impostazioni")

        # Sempre da DB per evitare cache stale sul POST
        imp = Impostazioni.objects.get_or_create(pk=1)[0]
        form_class = SEZIONE_FORM[sezione]
        form = form_class(request.POST, instance=imp)

        link_formset = None
        if sezione == "footer":
            link_formset = FooterLinkFormSet(request.POST, instance=imp)

        if form.is_valid():
            update_fields = list(form_class.Meta.fields)

            # Quando Gmail OAuth è attivo i campi SMTP manuali non vengono renderizzati
            # nell'HTML: arriverebbero vuoti e sovrascriverebbero i valori salvati.
            if sezione == "email" and imp.smtp_use_gmail_oauth:
                update_fields = [f for f in update_fields if f not in CAMPI_SMTP_MANUALI]

            saved = form.save(commit=False)
            saved.save(update_fields=[*update_fields, "aggiornato_at"])
            cache.set(Impostazioni.CACHE_KEY, saved, 300)

            if link_formset is not None:
                if link_formset.is_valid():
                    link_formset.save()
                    messages.success(request, "Footer salvato.")
                else:
                    messages.warning(
                        request,
                        "Testo footer salvato. Errore nei link: "
                        + str(link_formset.non_form_errors() or link_formset.errors),
                    )
            else:
                messages.success(request, f"{SEZIONE_LABEL.get(sezione, sezione)} salvato.")

            return redirect(f"{request.path}#{sezione}")

        # Form non valido: ri-renderizza mostrando gli errori nella sezione corretta
        ctx = self._build_context(
            imp,
            **{f"form_{sezione}": form},
            **({"link_formset": link_formset} if link_formset is not None else {}),
        )
        return render(request, self.template_name, ctx)


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


class AxesSbloccaView(RuoloRequiredMixin, View):
    """Sblocca uno o tutti gli AccessAttempt di axes."""

    ruoli_ammessi = (Ruolo.ADMIN,)

    def post(self, request):
        from axes.models import AccessAttempt

        attempt_pk = request.POST.get("attempt_pk")
        if attempt_pk == "tutti":
            count = AccessAttempt.objects.count()
            AccessAttempt.objects.all().delete()
            messages.success(request, f"Sbloccati tutti i {count} IP bloccati.")
        else:
            try:
                attempt = AccessAttempt.objects.get(pk=attempt_pk)
                ip = attempt.ip_address
                attempt.delete()
                messages.success(request, f"IP {ip} sbloccato.")
            except AccessAttempt.DoesNotExist:
                messages.error(request, "Tentativo non trovato.")
        return redirect("siteconfig:impostazioni")


class LogExportView(RuoloRequiredMixin, View):
    """Pagina dedicata ai log di generazione PDF/Excel."""

    template_name = "siteconfig/log_export.html"
    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def get(self, request):
        from apps.exports.models import LogTaskExport
        logs = LogTaskExport.objects.all()[:200]
        return render(request, self.template_name, {"log_export": logs})


class CachePdfView(RuoloRequiredMixin, View):
    """Gestione cache PDF diari: lista, invalidazione singola/totale, generazione massiva."""

    template_name = "siteconfig/cache_pdf.html"
    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def get(self, request):
        from django.core.cache import cache

        from apps.editions.models import Edizione
        from apps.exports.tasks import lock_key_massivo
        from apps.storage_drive.models import DriveFile, TipoFile

        edizioni = Edizione.objects.order_by("-anno").prefetch_related(
            "diari"
        )
        cache_per_edizione = []
        for ed in edizioni:
            files = DriveFile.objects.filter(
                tipo=TipoFile.PDF, diario__edizione=ed
            ).select_related("diario__squadriglia").order_by(
                "diario__squadriglia__nome"
            )
            if files.exists():
                cache_per_edizione.append({
                    "edizione": ed,
                    "files": files,
                    "bulk_lock": bool(cache.get(lock_key_massivo(ed.pk))),
                })

        edizioni_disponibili = list(Edizione.objects.order_by("-anno"))
        locks_attivi = {
            ed.pk: bool(cache.get(lock_key_massivo(ed.pk)))
            for ed in edizioni_disponibili
        }
        return render(request, self.template_name, {
            "cache_per_edizione": cache_per_edizione,
            "edizioni_disponibili": edizioni_disponibili,
            "locks_attivi": locks_attivi,
        })

    def post(self, request):
        from django.core.cache import cache

        from apps.exports.tasks import lock_key_massivo, task_genera_pdf_massivo
        from apps.storage_drive.models import DriveFile, TipoFile

        azione = request.POST.get("azione")

        if azione == "invalida_singolo":
            file_pk = request.POST.get("file_pk")
            try:
                f = DriveFile.objects.get(pk=file_pk, tipo=TipoFile.PDF)
                diario_str = str(f.diario.squadriglia) if f.diario else str(f)
                f.delete()
                messages.success(request, f"Cache PDF eliminata per {diario_str}.")
            except DriveFile.DoesNotExist:
                messages.error(request, "File non trovato.")

        elif azione == "invalida_edizione":
            edizione_pk = request.POST.get("edizione_pk")
            count = DriveFile.objects.filter(
                tipo=TipoFile.PDF, diario__edizione_id=edizione_pk
            ).delete()[0]
            messages.success(request, f"Eliminati {count} PDF dalla cache.")

        elif azione == "invalida_tutti":
            count = DriveFile.objects.filter(tipo=TipoFile.PDF).delete()[0]
            messages.success(request, f"Eliminati tutti i {count} PDF dalla cache.")

        elif azione == "genera_massivo":
            edizione_pk = request.POST.get("edizione_pk")
            if not edizione_pk:
                messages.error(request, "Seleziona un'edizione.")
                return redirect("siteconfig:cache_pdf")
            edizione_pk = int(edizione_pk)
            if cache.get(lock_key_massivo(edizione_pk)):
                messages.warning(request, "Generazione massiva già in corso per questa edizione.")
                return redirect("siteconfig:cache_pdf")
            cache.set(lock_key_massivo(edizione_pk), True, 7200)
            task_genera_pdf_massivo.delay(edizione_pk, request.user.pk)
            messages.success(
                request,
                "Generazione massiva avviata. Riceverai una mail al termine. "
                "Durante la generazione i PDF singoli per questa edizione sono disabilitati.",
            )

        return redirect("siteconfig:cache_pdf")


class TestEmailView(RuoloRequiredMixin, View):
    """Invia un'email di test tramite SMTP o provider transazionale."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request):
        from django.core.mail import EmailMessage
        from django.urls import reverse

        from apps.siteconfig.email_backends import _smtp_backend, _transazionale_backend
        from apps.siteconfig.models import Impostazioni

        imp = Impostazioni.get()
        backend_tipo = request.POST.get("backend", "smtp")  # "smtp" | "transazionale"

        try:
            if backend_tipo == "transazionale":
                conn = _transazionale_backend(imp, fail_silently=False)
                label = "provider transazionale"
            else:
                conn = _smtp_backend(imp, fail_silently=False)
                label = "SMTP"

            msg = EmailMessage(
                subject=f"Test invio email ({label}) — {imp.titolo or 'Plancia'}",
                body=(
                    f"Questo è un messaggio di test inviato tramite {label} "
                    "dalle impostazioni di Plancia.\n"
                    "Se lo ricevi, la configurazione funziona correttamente."
                ),
                from_email=imp.from_email,
                to=[request.user.email],
                connection=conn,
            )
            msg.send()
            messages.success(
                request,
                f"Email di test ({label}) inviata a {request.user.email}.",
            )
        except Exception as exc:
            messages.error(request, f"Errore nell'invio ({label}): {exc}")
        return redirect(reverse("siteconfig:impostazioni") + "#email")


GMAIL_SMTP_SCOPES = [
    "https://mail.google.com/",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GmailSMTPOAuthInitView(RuoloRequiredMixin, View):
    """Avvia il flusso OAuth Google per Gmail SMTP (scope mail.google.com)."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def get(self, request):
        import base64
        import hashlib
        import secrets

        from google_auth_oauthlib.flow import Flow

        code_verifier = secrets.token_urlsafe(96)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_GMAIL_SMTP_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GMAIL_SMTP_SCOPES,
            redirect_uri=settings.GOOGLE_GMAIL_SMTP_REDIRECT_URI,
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
        request.session["gmail_smtp_oauth_state"] = state
        request.session["gmail_smtp_oauth_code_verifier"] = code_verifier
        return redirect(auth_url)


class GmailSMTPOAuthCallbackView(View):
    """Callback OAuth Gmail SMTP: scambia il codice e salva GmailSMTPCredenziali."""

    def get(self, request):
        import os

        from django.utils import timezone
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build

        from apps.siteconfig.models import GmailSMTPCredenziali, Impostazioni

        state = request.session.pop("gmail_smtp_oauth_state", None)
        code_verifier = request.session.pop("gmail_smtp_oauth_code_verifier", None)

        if not state or state != request.GET.get("state"):
            messages.error(request, "Sessione OAuth non valida. Riprova.")
            return redirect("siteconfig:impostazioni")

        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_GMAIL_SMTP_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GMAIL_SMTP_SCOPES,
            state=state,
            redirect_uri=settings.GOOGLE_GMAIL_SMTP_REDIRECT_URI,
        )
        flow.fetch_token(
            authorization_response=request.build_absolute_uri(),
            code_verifier=code_verifier,
        )
        creds = flow.credentials

        service = build("oauth2", "v2", credentials=creds)
        email = service.userinfo().get().execute().get("email", "")

        expires_at = None
        if creds.expiry:
            expires_at = (
                timezone.make_aware(creds.expiry)
                if creds.expiry.tzinfo is None
                else creds.expiry
            )

        GmailSMTPCredenziali.objects.update_or_create(
            account_email=email,
            defaults={
                "access_token": creds.token,
                "refresh_token": creds.refresh_token or "",
                "expires_at": expires_at,
            },
        )

        imp = Impostazioni.get()
        imp.smtp_gmail_account = email
        imp.smtp_use_gmail_oauth = True
        imp.save(update_fields=["smtp_gmail_account", "smtp_use_gmail_oauth", "aggiornato_at"])

        messages.success(request, f"Account Gmail {email} collegato per SMTP OAuth.")
        return redirect("siteconfig:impostazioni")


class GmailSMTPOAuthDisconnectView(RuoloRequiredMixin, View):
    """Scollega l'account Gmail OAuth e disabilita Gmail SMTP."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request):
        from apps.siteconfig.models import GmailSMTPCredenziali, Impostazioni

        imp = Impostazioni.get()
        if imp.smtp_gmail_account:
            GmailSMTPCredenziali.objects.filter(account_email=imp.smtp_gmail_account).delete()
        imp.smtp_use_gmail_oauth = False
        imp.smtp_gmail_account = ""
        imp.save(update_fields=["smtp_use_gmail_oauth", "smtp_gmail_account", "aggiornato_at"])
        messages.success(request, "Account Gmail scollegato.")
        return redirect("siteconfig:impostazioni")


class PaginaStaticaPublicView(View):
    """Pagina pubblica (privacy / termini). Non richiede autenticazione."""

    def get(self, request, slug):
        try:
            SlugPagina(slug)
        except ValueError:
            from django.http import Http404
            raise Http404 from None

        pagina = PaginaStatica.objects.filter(slug=slug).first()
        if not pagina:
            # Mostra pagina vuota con titolo di default
            pagina = PaginaStatica(
                slug=slug,
                titolo=SlugPagina(slug).label,
                contenuto="<p>Contenuto non ancora disponibile.</p>",
            )
        return render(request, "siteconfig/pagina_statica.html", {"pagina": pagina})


class PaginaStaticaEditView(RuoloRequiredMixin, View):
    """Modifica del contenuto di una pagina statica. Solo Admin/Segreteria/IABR."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def _get_or_init(self, slug):
        try:
            SlugPagina(slug)
        except ValueError:
            from django.http import Http404
            raise Http404 from None
        pagina, _ = PaginaStatica.objects.get_or_create(
            slug=slug,
            defaults={"titolo": SlugPagina(slug).label, "contenuto": ""},
        )
        return pagina

    def get(self, request, slug):
        pagina = self._get_or_init(slug)
        form = PaginaStaticaForm(instance=pagina)
        return render(request, "siteconfig/pagina_statica_edit.html", {
            "form": form,
            "pagina": pagina,
            "slug": slug,
        })

    def post(self, request, slug):
        pagina = self._get_or_init(slug)
        form = PaginaStaticaForm(request.POST, instance=pagina)
        if form.is_valid():
            form.save()
            messages.success(request, f"Pagina «{pagina.get_slug_display()}» aggiornata.")
            return redirect("siteconfig:pagina_edit", slug=slug)
        return render(request, "siteconfig/pagina_statica_edit.html", {
            "form": form,
            "pagina": pagina,
            "slug": slug,
        })


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(csrf_exempt, name="dispatch")
class FlowerProxyView(View):
    """Proxy verso Flower (dashboard Celery) accessibile su /celery/.

    Solo Admin. Flower deve essere avviato con il profilo 'flower':
      COMPOSE_PROFILES=flower docker compose --env-file .env.prod up -d
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

    def _proxy(self, request, path):
        import urllib.error
        import urllib.request
        from urllib.parse import urlencode

        from django.http import HttpResponse

        flower_base = getattr(settings, "FLOWER_INTERNAL_URL", "http://flower:5555").rstrip("/")
        target_path = f"/celery/{path}" if path else "/celery/"
        target_url = flower_base + target_path
        if request.GET:
            target_url += "?" + urlencode(request.GET)

        headers = {}
        for name in ("Accept", "Accept-Encoding", "X-Requested-With"):
            if name in request.headers:
                headers[name] = request.headers[name]

        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
                content_type = resp.headers.get("Content-Type", "text/html")
                return HttpResponse(content, status=resp.status, content_type=content_type)
        except urllib.error.HTTPError as e:
            return HttpResponse(e.read(), status=e.code)
        except Exception as e:
            return HttpResponse(
                "<h1>Flower non raggiungibile</h1>"
                f"<pre>{e}</pre>"
                "<p>Avvia Flower con il profilo <code>flower</code>:<br>"
                "<code>COMPOSE_PROFILES=flower docker compose --env-file .env.prod up -d</code></p>",
                status=503,
                content_type="text/html",
            )


@method_decorator(csrf_exempt, name="dispatch")
class MailpitProxyView(View):
    """Proxy verso Mailpit per il debug delle email in produzione.

    Accessibile su /mailadmin/ solo per utenti staff. Richiede che Mailpit sia
    avviato con --ui-web-path /mailadmin e raggiungibile all'URL MAILPIT_INTERNAL_URL.
    csrf_exempt: l'autenticazione è gestita da dispatch(); le richieste Mailpit
    (PUT/PATCH per mark-as-read, DELETE, ecc.) non portano il token Django.
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

    def put(self, request, path=""):
        return self._proxy(request, path)

    def patch(self, request, path=""):
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
