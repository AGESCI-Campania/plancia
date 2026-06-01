# apps/notifications/admin.py
from django.contrib import admin

from apps.notifications.models import Invito, MailTemplate


@admin.register(MailTemplate)
class MailTemplateAdmin(admin.ModelAdmin):
    list_display = ("chiave", "oggetto", "attivo", "aggiornato_at")
    list_filter = ("attivo",)
    search_fields = ("chiave", "oggetto")
    readonly_fields = ("aggiornato_at", "tag_help")

    def tag_help(self, obj):
        from django.utils.html import format_html
        tags = ", ".join(f"{{{{ {t} }}}}" for t in obj.tag_disponibili)
        return format_html("<code>{}</code>", tags) if tags else "—"
    tag_help.short_description = "Tag disponibili"

    fieldsets = (
        (None, {"fields": ("chiave", "attivo")}),
        ("Contenuto", {"fields": ("oggetto", "corpo_html")}),
        ("Tag disponibili", {"fields": ("tag_help",)}),
        ("Timestamp", {"fields": ("aggiornato_at",), "classes": ("collapse",)}),
    )

    class Media:
        # tinymce per il corpo HTML
        js = ("tinymce/tinymce.min.js",)


@admin.register(Invito)
class InvitoAdmin(admin.ModelAdmin):
    list_display = ("utente", "ruolo_target", "diario", "stato", "inviato_at", "attivato_at")
    list_filter = ("ruolo_target", "stato")
    search_fields = ("utente__email", "diario__squadriglia__nome")
    readonly_fields = ("token", "inviato_at", "attivato_at")
    raw_id_fields = ["diario"]
    autocomplete_fields = ["utente"]
