# apps/exports/models.py
from django.db import models


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
