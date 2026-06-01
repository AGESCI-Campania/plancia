# apps/diaries/admin.py
from django.contrib import admin

from apps.diaries.models import (
    Allegato,
    Anagrafica,
    Diario,
    EsitoSpecialita,
    Impresa,
    MembroSq,
    Missione,
    PostoAzione,
    PostoAzioneMissione,
    Presentazione,
    RelazioneFinale,
    StatoDiario,
)


class AnagraficaInline(admin.StackedInline):
    model = Anagrafica
    extra = 0
    can_delete = False


class PresentazioneInline(admin.StackedInline):
    model = Presentazione
    extra = 0
    can_delete = False


class ImpresaInline(admin.TabularInline):
    model = Impresa
    extra = 0
    fields = ("numero", "titolo", "data_inizio", "data_fine", "link_esterno")
    show_change_link = True


class RelazioneFinaleInline(admin.StackedInline):
    model = RelazioneFinale
    extra = 0
    can_delete = False


class AllegatoInline(admin.TabularInline):
    model = Allegato
    extra = 0
    fields = ("modulo", "nome", "stato_sync", "caricato_da", "creato_at")
    readonly_fields = ("creato_at",)


@admin.register(Diario)
class DiarioAdmin(admin.ModelAdmin):
    list_display = (
        "squadriglia", "edizione", "tipo", "stato",
        "scadenza_riferimento", "csq", "crp", "is_pubblicato",
    )
    list_filter = ("edizione", "stato", "tipo", "scadenza_riferimento")
    search_fields = (
        "squadriglia__nome",
        "csq__cognome", "csq__nome",
        "crp__cognome", "crp__nome",
    )
    autocomplete_fields = ["squadriglia", "csq", "crp"]
    raw_id_fields = ["edizione"]
    readonly_fields = (
        "stato", "creato_at", "aggiornato_at",
        "inviato_at", "csq_completato_at", "pubblicato_at",
    )
    fieldsets = (
        (None, {"fields": ("edizione", "squadriglia", "tipo", "scadenza_riferimento")}),
        ("Persone", {"fields": ("csq", "crp")}),
        ("Stato", {
            "fields": ("stato", "inviato_at", "csq_completato_at", "pubblicato_at"),
        }),
        ("Timestamp", {"fields": ("creato_at", "aggiornato_at"), "classes": ("collapse",)}),
    )
    inlines = [AnagraficaInline, PresentazioneInline, ImpresaInline, RelazioneFinaleInline, AllegatoInline]
    actions = ["invia_diari", "avvia_valutazione"]

    @admin.display(description="pubblicato", boolean=True)
    def is_pubblicato(self, obj):
        return obj.pubblicato_at is not None

    @admin.action(description="Invia diari (In compilazione → Inviato)")
    def invia_diari(self, request, queryset):
        for d in queryset.filter(stato=StatoDiario.IN_COMPILAZIONE):
            try:
                d.invia()
            except ValueError:
                pass

    @admin.action(description="Avvia valutazione (Inviato → In valutazione)")
    def avvia_valutazione(self, request, queryset):
        for d in queryset.filter(stato=StatoDiario.INVIATO):
            try:
                d.avvia_valutazione()
            except ValueError:
                pass


class PostoAzioneInline(admin.TabularInline):
    model = PostoAzione
    extra = 1


class EsitoSpecialitaInline(admin.TabularInline):
    model = EsitoSpecialita
    extra = 1


@admin.register(Impresa)
class ImpresaAdmin(admin.ModelAdmin):
    list_display = ("diario", "numero", "titolo", "data_inizio", "data_fine")
    list_filter = ("numero", "diario__edizione")
    search_fields = ("titolo", "diario__squadriglia__nome")
    raw_id_fields = ["diario"]
    inlines = [PostoAzioneInline, EsitoSpecialitaInline]


class MembroSqInline(admin.TabularInline):
    model = MembroSq
    extra = 1


@admin.register(Presentazione)
class PresentazioneAdmin(admin.ModelAdmin):
    list_display = ("diario",)
    search_fields = ("diario__squadriglia__nome",)
    raw_id_fields = ["diario"]
    inlines = [MembroSqInline]


class PostoAzioneMissioneInline(admin.TabularInline):
    model = PostoAzioneMissione
    extra = 1


@admin.register(Missione)
class MissioneAdmin(admin.ModelAdmin):
    list_display = ("diario", "titolo", "data")
    search_fields = ("titolo", "diario__squadriglia__nome")
    raw_id_fields = ["diario"]
    inlines = [PostoAzioneMissioneInline]


@admin.register(RelazioneFinale)
class RelazioneFinaleAdmin(admin.ModelAdmin):
    list_display = ("diario", "specialita_conquistata", "aggiornato_at")
    search_fields = ("diario__squadriglia__nome",)
    raw_id_fields = ["diario"]
