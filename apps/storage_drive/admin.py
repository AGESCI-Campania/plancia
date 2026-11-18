# apps/storage_drive/admin.py
"""Admin per le credenziali OAuth di Drive e i file caricati.

I token non si mostrano: le credenziali si creano solo dal collegamento OAuth (SPA) e qui
si possono solo consultare o eliminare per scollegare un account.
"""
from django.contrib import admin

from apps.storage_drive.models import DriveCredenziali, DriveFile


@admin.register(DriveCredenziali)
class DriveCredenzialiAdmin(admin.ModelAdmin):
    list_display = ["account_email", "expires_at", "aggiornato_at"]
    search_fields = ["account_email"]
    fields = ["account_email", "expires_at", "aggiornato_at"]
    readonly_fields = ["account_email", "expires_at", "aggiornato_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DriveFile)
class DriveFileAdmin(admin.ModelAdmin):
    list_display = ["nome", "tipo", "edizione", "diario", "caricato_at"]
    list_filter = ["tipo", "edizione"]
    search_fields = ["nome", "drive_file_id"]
    list_select_related = ["edizione", "diario__squadriglia"]
    readonly_fields = [f.name for f in DriveFile._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
