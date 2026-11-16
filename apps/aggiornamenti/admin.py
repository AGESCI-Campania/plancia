from django.contrib import admin

from apps.aggiornamenti.models import ReleaseGitHub, RichiestaAggiornamento


@admin.register(ReleaseGitHub)
class ReleaseGitHubAdmin(admin.ModelAdmin):
    list_display = ("versione", "pubblicata_at", "controllata_at", "errore")
    readonly_fields = ("controllata_at",)


@admin.register(RichiestaAggiornamento)
class RichiestaAggiornamentoAdmin(admin.ModelAdmin):
    list_display = ("pk", "versione", "versione_partenza", "richiesta_da_email", "richiesta_at",
                    "stato", "completato_at")
    list_filter = ("stato",)
    readonly_fields = [f.name for f in RichiestaAggiornamento._meta.fields]

    def has_add_permission(self, request):
        return False
