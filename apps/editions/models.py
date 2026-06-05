# apps/editions/models.py
from django.db import models
from django.utils import timezone

CARTELLA_DIARIO_FORMAT_DEFAULT = (
    "{id_univoco}_{edizione}_{nome_gruppo}_{nome_reparto}_{nome_squadriglia}_{specialita}"
)


class StatoEdizione(models.TextChoices):
    BOZZA = "bozza", "Bozza"
    APERTA = "aperta", "Aperta"
    IN_VALUTAZIONE = "in_valutazione", "In valutazione"
    CHIUSA = "chiusa", "Chiusa"


class Edizione(models.Model):
    """Un'annata dei Guidoncini Verdi. Vedi docs sez. 4 e 7."""

    anno = models.PositiveIntegerField(unique=True, verbose_name="anno")
    stato = models.CharField(
        max_length=20, choices=StatoEdizione.choices, default=StatoEdizione.BOZZA
    )
    scadenza_evento = models.DateField(
        null=True, blank=True, verbose_name="prima scadenza (evento)"
    )
    scadenza_assemblea = models.DateField(
        null=True, blank=True, verbose_name="seconda scadenza (assemblea)"
    )
    data_evento_inizio = models.DateField(
        null=True, blank=True, verbose_name="inizio evento Guidoncini Verdi"
    )
    data_evento_fine = models.DateField(
        null=True, blank=True, verbose_name="fine evento Guidoncini Verdi"
    )
    evento_comune = models.CharField(
        max_length=120, blank=True, verbose_name="comune"
    )
    evento_localita = models.CharField(
        max_length=200, blank=True, verbose_name="località (opzionale)"
    )

    # Google Drive
    drive_folder_allegati_id = models.CharField(
        max_length=200, blank=True, verbose_name="ID cartella Drive allegati"
    )
    drive_folder_output_id = models.CharField(
        max_length=200, blank=True, verbose_name="ID cartella Drive output"
    )
    drive_oauth_account = models.EmailField(blank=True, verbose_name="account OAuth Drive")
    cartella_diario_format = models.CharField(
        max_length=300,
        blank=True,
        default=CARTELLA_DIARIO_FORMAT_DEFAULT,
        verbose_name="formato nome cartella diario",
        help_text=(
            "Variabili: {id_univoco} {edizione} {nome_gruppo} {nome_zona} "
            "{nome_reparto} {nome_squadriglia} {specialita}. "
            "{id_univoco} è obbligatorio."
        ),
    )

    creato_at = models.DateTimeField(auto_now_add=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-anno"]
        verbose_name = "edizione"
        verbose_name_plural = "edizioni"

    def __str__(self) -> str:
        return f"Edizione {self.anno}"

    @property
    def cartelle_configurate(self) -> bool:
        """True quando le cartelle Drive e il formato sono tutti impostati (lock attivo)."""
        return bool(
            self.drive_folder_allegati_id
            and self.drive_folder_output_id
            and self.cartella_diario_format
        )

    @property
    def scadenza_corrente(self) -> str:
        """'prima' finché non è passata la scadenza evento, poi 'seconda'."""
        oggi = timezone.now().date()
        if self.scadenza_evento and oggi <= self.scadenza_evento:
            return "prima"
        return "seconda"

    @property
    def seconda_scadenza_passata(self) -> bool:
        oggi = timezone.now().date()
        return bool(self.scadenza_assemblea and oggi > self.scadenza_assemblea)

    # --- Transizioni di stato -----------------------------------------------

    def apri(self) -> None:
        if self.stato != StatoEdizione.BOZZA:
            raise ValueError("Solo una bozza può essere aperta.")
        self.stato = StatoEdizione.APERTA
        self.save()

    def avvia_valutazione(self) -> None:
        if self.stato != StatoEdizione.APERTA:
            raise ValueError("Solo un'edizione aperta può passare in valutazione.")
        self.stato = StatoEdizione.IN_VALUTAZIONE
        self.save()

    def chiudi(self) -> None:
        if self.stato != StatoEdizione.IN_VALUTAZIONE:
            raise ValueError("Solo un'edizione in valutazione può essere chiusa.")
        self.stato = StatoEdizione.CHIUSA
        self.save()


class Dilazione(models.Model):
    """Proroga individuale concessa a una squadriglia per una edizione. Vedi docs sez. 7."""

    diario = models.ForeignKey(
        "diaries.Diario", on_delete=models.CASCADE, related_name="dilazioni"
    )
    nuova_scadenza = models.DateField(verbose_name="nuova scadenza")
    motivazione = models.TextField()
    concessa_da = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="dilazioni_concesse"
    )
    creata_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creata_at"]
        verbose_name = "dilazione"
        verbose_name_plural = "dilazioni"

    def __str__(self) -> str:
        return f"Dilazione {self.diario} → {self.nuova_scadenza}"
