# apps/imports/models.py
from django.db import models


class TipoImport(models.TextChoices):
    COCA = "coca", "Capi (Co.Ca.)"
    RAGAZZI = "ragazzi", "Ragazzi"
    SQUADRIGLIE = "squadriglie", "Squadriglie iscritte"


class StatoMatch(models.TextChoices):
    OK = "ok", "Associato"
    DA_RICONCILIARE = "da_riconciliare", "Da riconciliare"
    SCARTATA = "scartata", "Scartata"


class LogImportazione(models.Model):
    """Esito di un import. Le righe 'da_riconciliare' alimentano la schermata
    di riconciliazione manuale (docs sez. 14)."""

    tipo = models.CharField(max_length=20, choices=TipoImport.choices)
    file_nome = models.CharField(max_length=255)
    edizione = models.ForeignKey(
        "editions.Edizione",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_log",
        help_text="Valorizzato solo per import squadriglie iscritte.",
    )
    creato_da = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="import_eseguiti"
    )
    creato_at = models.DateTimeField(auto_now_add=True)
    totale = models.PositiveIntegerField(default=0)
    ok = models.PositiveIntegerField(default=0)
    scartati = models.PositiveIntegerField(default=0)
    da_riconciliare = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.file_nome} ({self.creato_at:%Y-%m-%d %H:%M})"


class RigaImportazione(models.Model):
    log = models.ForeignKey(LogImportazione, on_delete=models.CASCADE, related_name="righe")
    numero = models.PositiveIntegerField()
    dati_grezzi = models.JSONField(default=dict)
    stato_match = models.CharField(max_length=20, choices=StatoMatch.choices)
    socio_match = models.ForeignKey(
        "org.Socio", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=255, blank=True)
