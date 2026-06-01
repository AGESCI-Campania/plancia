# apps/exports/admin.py
from django.contrib import admin

from apps.exports.models import PdfTemplate


@admin.register(PdfTemplate)
class PdfTemplateAdmin(admin.ModelAdmin):
    list_display = ("chiave", "versione", "attivo", "aggiornato_at")
    list_filter = ("attivo",)
    readonly_fields = ("versione", "aggiornato_at")
