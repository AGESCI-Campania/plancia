from django.apps import AppConfig


class DiariesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.diaries"
    label = "diaries"

    def ready(self) -> None:
        from django.db.models.signals import post_save

        from apps.diaries.models import Anagrafica, Diario, Impresa, Missione, Presentazione

        def _invalida_cache_pdf(sender, instance, **kwargs):
            """Elimina il DriveFile PDF del diario quando un modulo viene aggiornato."""
            try:
                from apps.storage_drive.models import DriveFile, TipoFile

                diario_pk = instance.pk if sender == Diario else instance.diario_id
                DriveFile.objects.filter(diario_id=diario_pk, tipo=TipoFile.PDF).delete()
            except Exception:
                pass

        for model in (Diario, Anagrafica, Presentazione, Impresa, Missione):
            post_save.connect(_invalida_cache_pdf, sender=model, weak=False)
