# apps/siteconfig/views.py
"""Vista dedicata Impostazioni fuori dall'admin (Admin/IABR/Segreteria)."""
from __future__ import annotations

import os

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
from apps.siteconfig import services
from apps.siteconfig.forms import (
    SEZIONE_FORM,
    SEZIONE_LABEL,
    FooterLinkFormSet,
    MailTemplateForm,
    PaginaStaticaForm,
)
from apps.siteconfig.models import Impostazioni


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
            # Con Gmail OAuth attivo i campi SMTP manuali non vengono renderizzati
            # nell'HTML: salva_sezione non li sovrascrive.
            services.salva_sezione(form, sezione)

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
    """Riceve il file caricato dall'utente, lo salva su disco e accoda il task Celery.

    Logica in `apps.imports.services.lancia_import` (condivisa con l'API).
    """

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request, tracciato):
        from django.core.exceptions import ValidationError

        from apps.imports.services import lancia_import

        try:
            esito = lancia_import(
                tracciato, request.FILES.get("file"), request.POST.get("edizione_pk")
            )
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return redirect("imports:log_list")
        messages.success(request, esito.messaggio)
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
        return {
            "form": form,
            "chiave": chiave,
            "tag_disponibili": [{"nome": t, "tpl": "{{ " + t + " }}"} for t in tags],
            "instance": instance,
            "chiavi_senza_record": services.chiavi_senza_record(esclusa=chiave),
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

        _tpl, trovato = services.importa_mail_template(chiave)
        if not trovato:
            messages.warning(request, f"File mail/{chiave}.html non trovato: template creato vuoto.")
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
        services.copia_mail_template(source.chiave, target_chiave)
        messages.success(request, f"Template «{target_chiave}» creato da «{chiave}».")
        return redirect("siteconfig:mail_template_edit", chiave=target_chiave)


@method_decorator(csrf_exempt, name="dispatch")
class MailTemplateImageUploadView(RuoloRequiredMixin, View):
    """Endpoint upload immagini per TinyMCE nei template email."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request):
        from django.core.exceptions import ValidationError

        try:
            percorso = services.salva_immagine_mail(request.FILES.get("file"))
        except ValidationError as exc:
            return JsonResponse({"error": exc.messages[0]}, status=400)
        return JsonResponse({"location": request.build_absolute_uri(percorso)})


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
            count = services.sblocca_accessi()
            messages.success(request, f"Sbloccati tutti i {count} IP bloccati.")
        else:
            try:
                ip = AccessAttempt.objects.get(pk=attempt_pk).ip_address
                services.sblocca_accessi(int(attempt_pk))
                messages.success(request, f"IP {ip} sbloccato.")
            except (AccessAttempt.DoesNotExist, ValueError, TypeError):
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
        edizioni_con_lock = [
            (ed, bool(cache.get(lock_key_massivo(ed.pk))))
            for ed in edizioni_disponibili
        ]
        edizioni_in_corso = [
            {"edizione": ed, "task_id": cache.get(f"pdf_massivo_task_id:{ed.pk}")}
            for ed in edizioni_disponibili
            if cache.get(lock_key_massivo(ed.pk)) and cache.get(f"pdf_massivo_task_id:{ed.pk}")
        ]
        return render(request, self.template_name, {
            "cache_per_edizione": cache_per_edizione,
            "edizioni_con_lock": edizioni_con_lock,
            "edizioni_in_corso": edizioni_in_corso,
        })

    def post(self, request):
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
            count = services.invalida_cache_pdf(int(edizione_pk)) if edizione_pk else 0
            messages.success(request, f"Eliminati {count} PDF dalla cache.")

        elif azione == "invalida_tutti":
            count = services.invalida_cache_pdf()
            messages.success(request, f"Eliminati tutti i {count} PDF dalla cache.")

        elif azione == "genera_massivo":
            from django.core.exceptions import ValidationError

            edizione_pk = request.POST.get("edizione_pk")
            if not edizione_pk:
                messages.error(request, "Seleziona un'edizione.")
                return redirect("siteconfig:cache_pdf")
            try:
                services.avvia_pdf_massivo(int(edizione_pk), request.user.pk)
            except ValidationError as exc:
                messages.warning(request, exc.messages[0])
                return redirect("siteconfig:cache_pdf")
            messages.success(
                request,
                "Generazione massiva avviata. Riceverai una mail al termine. "
                "Durante la generazione i PDF singoli per questa edizione sono disabilitati.",
            )

        elif azione == "interrompi_massivo":
            edizione_pk = request.POST.get("edizione_pk")
            if edizione_pk:
                services.interrompi_pdf_massivo(int(edizione_pk))
                messages.info(
                    request,
                    "Interruzione richiesta. Il task si fermerà dopo il diario in corso.",
                )

        return redirect("siteconfig:cache_pdf")


class TestEmailView(RuoloRequiredMixin, View):
    """Invia un'email di test tramite SMTP o provider transazionale."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request):
        from django.urls import reverse

        backend_tipo = request.POST.get("backend", "smtp")  # "smtp" | "transazionale"
        label = "provider transazionale" if backend_tipo == "transazionale" else "SMTP"
        try:
            services.invia_email_test(backend_tipo, request.user.email)
            messages.success(
                request,
                f"Email di test ({label}) inviata a {request.user.email}.",
            )
        except Exception as exc:
            messages.error(request, f"Errore nell'invio ({label}): {exc}")
        return redirect(reverse("siteconfig:impostazioni") + "#email")


GMAIL_SMTP_SCOPES = services.GMAIL_SMTP_SCOPES

# Pagina della SPA a cui torna la callback quando il flusso è partito dall'API.
SPA_IMPOSTAZIONI_EMAIL = "/impostazioni/email"


class GmailSMTPOAuthInitView(RuoloRequiredMixin, View):
    """Avvia il flusso OAuth Google per Gmail SMTP (scope mail.google.com)."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def get(self, request):
        return redirect(services.url_autorizzazione_gmail(request.session, origine="web"))


class GmailSMTPOAuthCallbackView(View):
    """Callback OAuth Gmail SMTP: scambia il codice e salva GmailSMTPCredenziali.

    Resta sullo stesso percorso (registrato presso Google). Se il flusso è partito
    dall'API (SPA) rimanda a `/impostazioni/email?esito=ok|errore&messaggio=...`,
    altrimenti alla pagina Impostazioni Django.
    """

    def get(self, request):
        import logging
        from urllib.parse import urlencode

        from django.core.exceptions import ValidationError

        spa = request.session.pop(services.SESSIONE_GMAIL_ORIGINE, "web") == "spa"
        try:
            email = services.completa_oauth_gmail(
                request.session, request.GET.get("state"), request.build_absolute_uri()
            )
        except ValidationError as exc:
            esito, testo = "errore", exc.messages[0]
        except Exception as exc:  # errore di Google (consenso negato, codice non valido, …)
            logging.getLogger(__name__).exception("Callback Gmail SMTP OAuth fallita")
            esito, testo = "errore", f"Collegamento Gmail non riuscito: {exc}"
        else:
            esito, testo = "ok", f"Account Gmail {email} collegato per SMTP OAuth."

        if spa:
            query = urlencode({"esito": esito, "messaggio": testo})
            return redirect(f"{SPA_IMPOSTAZIONI_EMAIL}?{query}")
        (messages.success if esito == "ok" else messages.error)(request, testo)
        return redirect("siteconfig:impostazioni")


class GmailSMTPOAuthDisconnectView(RuoloRequiredMixin, View):
    """Scollega l'account Gmail OAuth e disabilita Gmail SMTP."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request):
        services.scollega_gmail()
        messages.success(request, "Account Gmail scollegato.")
        return redirect("siteconfig:impostazioni")


class PaginaStaticaPublicView(View):
    """Pagina pubblica (privacy / termini). Non richiede autenticazione."""

    def get(self, request, slug):
        pagina = services.pagina_pubblica(slug)
        return render(request, "siteconfig/pagina_statica.html", {"pagina": pagina})


class PaginaStaticaEditView(RuoloRequiredMixin, View):
    """Modifica del contenuto di una pagina statica. Solo Admin/Segreteria/IABR."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def get(self, request, slug):
        pagina = services.pagina_per_modifica(slug)
        form = PaginaStaticaForm(instance=pagina)
        return render(request, "siteconfig/pagina_statica_edit.html", {
            "form": form,
            "pagina": pagina,
            "slug": slug,
        })

    def post(self, request, slug):
        pagina = services.pagina_per_modifica(slug)
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


class PaginaStaticaImportaView(RuoloRequiredMixin, View):
    """Importa il contenuto predefinito da templates/siteconfig/default_pages/<slug>.html."""

    ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)

    def post(self, request, slug):
        from django.core.exceptions import ValidationError

        try:
            pagina = services.importa_pagina_predefinita(slug)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("siteconfig:pagina_edit", slug=slug)
        messages.success(request, f"Contenuto predefinito caricato per «{pagina.get_slug_display()}».")
        return redirect("siteconfig:pagina_edit", slug=slug)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(csrf_exempt, name="dispatch")
class FlowerProxyView(View):
    """Proxy verso Flower (dashboard Celery) accessibile su /celery/.

    Solo Admin. Flower deve essere avviato con il profilo 'flower':
      COMPOSE_PROFILES=flower in .env, poi docker compose up -d
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

        headers = {
            # Non passiamo Accept-Encoding: urllib non decomprime gzip e servirebbe
            # dati binari al browser invece di JSON/HTML leggibile.
            "Accept-Encoding": "identity",
        }
        for name in ("Accept", "X-Requested-With", "Content-Type"):
            if name in request.headers:
                headers[name] = request.headers[name]

        body = request.body if request.method in ("POST", "PUT", "PATCH") else None
        try:
            req = urllib.request.Request(target_url, data=body, headers=headers, method=request.method)
            with urllib.request.urlopen(req, timeout=15) as resp:
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
                "<code>COMPOSE_PROFILES=flower in .env, poi docker compose up -d</code></p>",
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
                "<p>Avvia Mailpit con il profilo <code>mailpit</code>:<br>"
                "<code>COMPOSE_PROFILES=mailpit</code> in <code>.env</code>, poi "
                "<code>docker compose up -d</code></p>",
                status=503,
                content_type="text/html",
            )
