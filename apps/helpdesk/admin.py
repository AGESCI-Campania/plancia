# apps/helpdesk/admin.py
from django.contrib import admin

from apps.helpdesk.models import RispostaTicket, StatoTicket, Ticket


class RispostaTicketInline(admin.TabularInline):
    model = RispostaTicket
    extra = 0
    fields = ("autore", "testo", "creata_at")
    readonly_fields = ("creata_at",)
    autocomplete_fields = ["autore"]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "pk", "oggetto", "categoria", "stato", "aperto_da", "assegnato_a",
        "diario", "creato_at",
    )
    list_filter = ("stato", "categoria")
    search_fields = ("oggetto", "aperto_da__email", "diario__squadriglia__nome")
    autocomplete_fields = ["aperto_da", "assegnato_a"]
    raw_id_fields = ["diario"]
    readonly_fields = ("creato_at", "aggiornato_at", "chiuso_at")
    inlines = [RispostaTicketInline]
    actions = ["prendi_in_carico", "chiudi_ticket"]

    @admin.action(description="Prendi in carico i ticket selezionati")
    def prendi_in_carico(self, request, queryset):
        for t in queryset.filter(stato=StatoTicket.APERTO):
            t.prendi_in_carico(request.user)

    @admin.action(description="Chiudi i ticket selezionati")
    def chiudi_ticket(self, request, queryset):
        for t in queryset.exclude(stato=StatoTicket.CHIUSO):
            t.chiudi(request.user)
