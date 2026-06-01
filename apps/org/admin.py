# apps/org/admin.py
from django.contrib import admin

from apps.org.models import Gruppo, Reparto, Socio, Squadriglia, Zona


class GruppoInline(admin.TabularInline):
    model = Gruppo
    extra = 0
    show_change_link = True


@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ("nome",)
    search_fields = ("nome",)
    inlines = [GruppoInline]


@admin.register(Gruppo)
class GruppoAdmin(admin.ModelAdmin):
    list_display = ("nome", "zona")
    list_filter = ("zona",)
    search_fields = ("nome", "zona__nome")
    autocomplete_fields = ["zona"]


class SquadrigliaInline(admin.TabularInline):
    model = Squadriglia
    extra = 0
    show_change_link = True


@admin.register(Reparto)
class RepartoAdmin(admin.ModelAdmin):
    list_display = ("nome", "gruppo")
    list_filter = ("gruppo__zona",)
    search_fields = ("nome", "gruppo__nome", "gruppo__zona__nome")
    autocomplete_fields = ["gruppo"]
    inlines = [SquadrigliaInline]


@admin.register(Squadriglia)
class SquadrigliaAdmin(admin.ModelAdmin):
    list_display = ("nome", "reparto")
    list_filter = ("reparto__gruppo__zona",)
    search_fields = ("nome", "reparto__nome", "reparto__gruppo__nome")
    autocomplete_fields = ["reparto"]


@admin.register(Socio)
class SocioAdmin(admin.ModelAdmin):
    list_display = ("codice_socio", "cognome", "nome", "categoria", "gruppo", "zona")
    list_filter = ("categoria", "zona", "gruppo")
    search_fields = ("codice_socio", "cognome", "nome", "email")
    autocomplete_fields = ["gruppo", "zona"]
    readonly_fields = ("codice_socio",)
    fieldsets = (
        (None, {"fields": ("codice_socio", "nome", "cognome", "categoria")}),
        ("Contatti", {"fields": ("email", "cellulare")}),
        ("Organizzazione", {"fields": ("zona", "gruppo")}),
        (
            "Dati accessori",
            {
                "fields": ("sesso", "data_nascita", "branca", "livello_foca", "status"),
                "classes": ("collapse",),
            },
        ),
    )
