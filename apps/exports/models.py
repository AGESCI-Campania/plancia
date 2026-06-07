# apps/exports/models.py
from django.db import models


class LogTaskExport(models.Model):
    """Log di esecuzione dei task Celery di generazione PDF/Excel."""

    class Tipo(models.TextChoices):
        PDF = "pdf", "PDF diario"
        EXCEL = "excel", "Excel edizione"
        PDF_MASSIVO = "pdf_massivo", "PDF massivo edizione"

    class Stato(models.TextChoices):
        OK = "ok", "Completato"
        ERRORE = "errore", "Errore"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    stato = models.CharField(max_length=20, choices=Stato.choices)
    messaggio = models.TextField(blank=True)
    traceback_testo = models.TextField(blank=True, verbose_name="traceback")
    diario_pk = models.IntegerField(null=True, blank=True)
    diario_str = models.CharField(max_length=200, blank=True)
    edizione_pk = models.IntegerField(null=True, blank=True)
    edizione_str = models.CharField(max_length=200, blank=True)
    utente_pk = models.IntegerField(null=True, blank=True)
    utente_str = models.CharField(max_length=200, blank=True)
    creato_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creato_at"]
        verbose_name = "Log export"
        verbose_name_plural = "Log export"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.get_stato_display()} — {self.creato_at:%d/%m/%Y %H:%M}"


class PdfTemplate(models.Model):
    """Template HTML per la generazione PDF (WeasyPrint).

    Scaricabile/caricabile da Impostazioni (docs sez. 15). Se non esiste un record
    attivo, si usa il file di default templates/exports/diario.html.
    Contesto disponibile: diario, anagrafica, imprese, missione, relazione, foto,
    esiti, titolo_piattaforma.
    """

    chiave = models.CharField(max_length=40, default="diario", unique=True)
    contenuto_html = models.TextField()
    versione = models.PositiveIntegerField(default=1)
    attivo = models.BooleanField(default=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.chiave} v{self.versione}"

# TODO (Claude Code): viste "scarica template" (default o attivo) e "carica template"
# (crea nuova versione attiva), riservate agli Admin in Impostazioni.
