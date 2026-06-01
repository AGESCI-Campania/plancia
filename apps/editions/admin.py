# apps/editions/admin.py
from django.contrib import admin

from apps.editions.models import Dilazione, Edizione, StatoEdizione


class DilazioneInline(admin.TabularInline):
    model = Dilazione
    extra = 0
    fields = ("nuova_scadenza", "motivazione", "concessa_da", "creata_at")
    readonly_fields = ("creata_at",)
    autocomplete_fields = ["concessa_da"]
    raw_id_fields = ["diario"]


@admin.register(Edizione)
class EdizioneAdmin(admin.ModelAdmin):
    list_display = (
        "anno", "stato", "scadenza_evento", "scadenza_assemblea",
        "data_evento_inizio", "data_evento_fine", "evento_comune", "num_diari",
    )
    list_filter = ("stato",)
    search_fields = ("anno",)
    readonly_fields = ("creato_at", "aggiornato_at")
    fieldsets = (
        (None, {"fields": ("anno", "stato")}),
        ("Scadenze", {"fields": ("scadenza_evento", "scadenza_assemblea")}),
        ("Evento Guidoncini Verdi", {
            "fields": ("data_evento_inizio", "data_evento_fine", "evento_comune", "evento_localita"),
        }),
        ("Google Drive", {
            "fields": ("drive_folder_allegati_id", "drive_folder_output_id", "drive_oauth_account"),
            "classes": ("collapse",),
        }),
        ("Timestamp", {"fields": ("creato_at", "aggiornato_at"), "classes": ("collapse",)}),
    )
    actions = ["apri_edizioni", "avvia_valutazione", "chiudi_edizioni"]

    @admin.display(description="diari")
    def num_diari(self, obj):
        return obj.diari.count()

    @admin.action(description="Apri edizioni selezionate (Bozza → Aperta)")
    def apri_edizioni(self, request, queryset):
        for ediz in queryset.filter(stato=StatoEdizione.BOZZA):
            ediz.apri()

    @admin.action(description="Avvia valutazione (Aperta → In valutazione)")
    def avvia_valutazione_edizioni(self, request, queryset):
        for ediz in queryset.filter(stato=StatoEdizione.APERTA):
            ediz.avvia_valutazione()

    @admin.action(description="Chiudi edizioni (In valutazione → Chiusa)")
    def chiudi_edizioni(self, request, queryset):
        for ediz in queryset.filter(stato=StatoEdizione.IN_VALUTAZIONE):
            ediz.chiudi()


@admin.register(Dilazione)
class DilazioneAdmin(admin.ModelAdmin):
    list_display = ("diario", "nuova_scadenza", "concessa_da", "creata_at")
    list_filter = ("diario__edizione",)
    search_fields = ("diario__squadriglia__nome",)
    autocomplete_fields = ["concessa_da"]
    raw_id_fields = ["diario"]
    readonly_fields = ("creata_at",)
