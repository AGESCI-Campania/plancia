# apps/storage_drive/models.py
from django.db import models


class TipoFile(models.TextChoices):
    FOTO = "foto", "Foto"
    PDF = "pdf", "PDF diario"
    EXCEL = "excel", "Excel esiti"


class DriveCredenziali(models.Model):
    """Token OAuth per l'account Drive di una edizione. Vedi docs sez. 10.

    I token vanno cifrati a riposo in produzione (TODO: campo cifrato).
    """

    account_email = models.EmailField(unique=True)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField(null=True, blank=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "credenziali Drive"
        verbose_name_plural = "credenziali Drive"

    def __str__(self) -> str:
        return self.account_email

    @property
    def scaduto(self) -> bool:
        from django.utils import timezone
        return bool(self.expires_at and timezone.now() >= self.expires_at)


class DriveFile(models.Model):
    """Riferimento locale a un file caricato su Google Drive. Vedi docs sez. 10."""

    drive_file_id = models.CharField(max_length=200, unique=True)
    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=10, choices=TipoFile.choices)
    mime = models.CharField(max_length=100, blank=True)
    dimensione = models.PositiveIntegerField(default=0)
    edizione = models.ForeignKey(
        "editions.Edizione",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drive_files",
    )
    diario = models.ForeignKey(
        "diaries.Diario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drive_files",
    )
    url_esterno = models.URLField(blank=True)
    caricato_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-caricato_at"]
        verbose_name = "file Drive"
        verbose_name_plural = "file Drive"

    def __str__(self) -> str:
        return f"{self.nome} ({self.tipo})"
