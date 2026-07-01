# apps/siteconfig/admin.py
"""Admin per Impostazioni singleton e template email/PDF."""
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from apps.siteconfig.models import Impostazioni


@admin.register(Impostazioni)
class ImpostazioniAdmin(admin.ModelAdmin):
    """Singleton: add è disabilitato, change punta sempre a pk=1."""

    fieldsets = [
        ("Identità piattaforma", {"fields": ["titolo", "sottotitolo"]}),
        ("Email (SMTP)", {
            "fields": ["email_mode", "from_name", "from_email", "smtp_host", "smtp_port",
                       "smtp_user", "smtp_password", "smtp_use_tls"],
            "classes": ["collapse"],
        }),
        ("API — rate limiting", {
            "fields": ["api_ratelimit_abilitato", "api_ratelimit_per_minuto", "api_ratelimit_per_ora"],
            "classes": ["collapse"],
        }),
        ("App version control", {
            "fields": ["app_versione_minima", "app_versione_deprecata", "app_messaggio_aggiornamento", "app_funzioni_limitate"],
            "classes": ["collapse"],
        }),
        ("Stato piattaforma", {"fields": ["manutenzione", "debug_toolbar", "debug_diagnostico"]}),
    ]
    readonly_fields = ["aggiornato_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(
            reverse("admin:siteconfig_impostazioni_change", args=[1])
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "lancia-import/<str:tracciato>/",
                self.admin_site.admin_view(self.lancia_import_view),
                name="siteconfig_lancia_import",
            ),
        ]
        return custom_urls + urls

    def lancia_import_view(self, request, tracciato):
        """Avvia il management command di import come task Celery (Admin/IABR/Segreteria)."""
        from apps.accounts.models import Ruolo
        ruoli_ammessi = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)
        if request.user.ruolo not in ruoli_ammessi and not request.user.is_superuser:
            messages.error(request, "Non hai i permessi per avviare questo import.")
            return HttpResponseRedirect(reverse("admin:siteconfig_impostazioni_change", args=[1]))

        tracciati_validi = {"coca", "ragazzi", "evento"}
        if tracciato not in tracciati_validi:
            messages.error(request, f"Tracciato '{tracciato}' non riconosciuto.")
            return HttpResponseRedirect(reverse("admin:siteconfig_impostazioni_change", args=[1]))

        from apps.imports.tasks import task_lancia_import
        task_lancia_import.delay(tracciato)
        messages.success(request, f"Import '{tracciato}' accodato.")
        return HttpResponseRedirect(reverse("admin:siteconfig_impostazioni_change", args=[1]))

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["tracciati"] = ["coca", "ragazzi", "evento"]
        return super().change_view(request, object_id, form_url, extra_context)
