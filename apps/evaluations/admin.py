# apps/evaluations/admin.py
from django.contrib import admin

from apps.evaluations.models import AssegnazionePGV, EsitoValutazione, Valutazione


class AssegnazionePGVInline(admin.TabularInline):
    model = AssegnazionePGV
    extra = 0
    fields = ("pgv", "assegnato_da", "creata_at")
    readonly_fields = ("creata_at",)
    autocomplete_fields = ["pgv", "assegnato_da"]
    fk_name = "valutazione"


@admin.register(Valutazione)
class ValutazioneAdmin(admin.ModelAdmin):
    list_display = (
        "diario", "esito", "stato", "valutatore", "confermata_da",
        "pubblicata", "creata_at",
    )
    list_filter = ("esito", "stato", "diario__edizione")
    search_fields = ("diario__squadriglia__nome", "valutatore__email")
    raw_id_fields = ["diario"]
    autocomplete_fields = ["valutatore", "confermata_da"]
    readonly_fields = ("creata_at", "aggiornata_at")
    fieldsets = (
        (None, {"fields": ("diario", "esito", "stato")}),
        ("Valutatori", {"fields": ("valutatore", "proposta_esito", "confermata_da")}),
        ("Note", {"fields": ("note",)}),
        ("Timestamp", {"fields": ("creata_at", "aggiornata_at"), "classes": ("collapse",)}),
    )
    inlines = [AssegnazionePGVInline]

    @admin.display(description="pubblicata", boolean=True)
    def pubblicata(self, obj):
        return obj.pubblicata


@admin.register(AssegnazionePGV)
class AssegnazionePGVAdmin(admin.ModelAdmin):
    list_display = ("valutazione", "pgv", "assegnato_da", "creata_at")
    list_filter = ("valutazione__diario__edizione",)
    search_fields = ("valutazione__diario__squadriglia__nome", "pgv__email")
    autocomplete_fields = ["pgv", "assegnato_da"]
    raw_id_fields = ["valutazione"]
