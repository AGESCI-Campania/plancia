# apps/evaluations/models.py
from django.db import models
from django.utils import timezone


class EsitoValutazione(models.TextChoices):
    APPROVATA = "approvata", "Approvata"
    NON_APPROVATA = "non_approvata", "Non approvata"
    MAGGIORI_INFO = "maggiori_info", "Maggiori informazioni richieste"


class StatoValutazione(models.TextChoices):
    ASSEGNATA = "assegnata", "Assegnata"
    IN_REVISIONE = "in_revisione", "In revisione (proposta PGV)"
    CONFERMATA = "confermata", "Confermata"


class Valutazione(models.Model):
    """Valutazione 0:1 con Diario. Vedi docs sez. 4, 6.

    Regole:
    - Incaricato EG valuta direttamente → esito definitivo (stato=CONFERMATA).
    - Membro PGV propone → stato=IN_REVISIONE per Approvata/Non approvata.
    - Maggiori informazioni non passa per IN_REVISIONE.
    - Gli Incaricati possono modificare l'esito fino alla pubblicazione.
    """

    diario = models.OneToOneField(
        "diaries.Diario", on_delete=models.CASCADE, related_name="valutazione"
    )
    esito = models.CharField(
        max_length=20, choices=EsitoValutazione.choices, null=True, blank=True
    )
    stato = models.CharField(
        max_length=20, choices=StatoValutazione.choices, default=StatoValutazione.ASSEGNATA
    )
    valutatore = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="valutazioni_espresse",
        verbose_name="valutatore",
    )
    confermata_da = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="valutazioni_confermate",
    )
    proposta_esito = models.CharField(
        max_length=20,
        choices=EsitoValutazione.choices,
        null=True,
        blank=True,
        help_text="Esito proposto da un membro PGV (in attesa di conferma Incaricato).",
    )
    note = models.TextField(blank=True)
    creata_at = models.DateTimeField(auto_now_add=True)
    aggiornata_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "valutazione"
        verbose_name_plural = "valutazioni"

    def __str__(self) -> str:
        return f"Valutazione {self.diario} — {self.esito or 'in corso'}"

    @property
    def pubblicata(self) -> bool:
        return self.diario.pubblicato_at is not None

    def _sync_diario_stato(self) -> None:
        """Allinea lo stato del Diario alle transizioni FSM. Chiamato dopo ogni modifica."""
        from apps.diaries.models import StatoDiario

        d = self.diario
        if self.esito == EsitoValutazione.APPROVATA and self.stato == StatoValutazione.CONFERMATA:
            if d.stato not in (StatoDiario.APPROVATO,):
                d.approva()
        elif self.esito == EsitoValutazione.NON_APPROVATA and self.stato == StatoValutazione.CONFERMATA:
            if d.stato not in (StatoDiario.NON_APPROVATO,):
                d.respingi()
        elif self.esito == EsitoValutazione.MAGGIORI_INFO:
            if d.stato not in (StatoDiario.MAGGIORI_INFO,):
                d.richiedi_info()
        elif self.stato == StatoValutazione.IN_REVISIONE:
            if d.stato != StatoDiario.IN_REVISIONE:
                d.proponi(self.proposta_esito)

    # --- Azioni ---------------------------------------------------------------

    def valuta_direttamente(self, utente, esito: str, note: str = "") -> None:
        """Incaricato EG valuta direttamente (esito definitivo)."""
        self.valutatore = utente
        self.esito = esito
        self.stato = StatoValutazione.CONFERMATA
        self.confermata_da = utente
        self.note = note
        self.save()
        self._sync_diario_stato()

    def proponi_pgv(self, pgv_utente, esito: str, note: str = "") -> None:
        """Membro PGV propone Approvata/Non approvata → IN_REVISIONE."""
        if esito == EsitoValutazione.MAGGIORI_INFO:
            raise ValueError("Maggiori informazioni non richiede proposta PGV.")
        self.valutatore = pgv_utente
        self.proposta_esito = esito
        self.stato = StatoValutazione.IN_REVISIONE
        self.note = note
        self.save()
        self._sync_diario_stato()

    def conferma(self, incaricato, note: str = "") -> None:
        """Incaricato conferma la proposta PGV."""
        if self.stato != StatoValutazione.IN_REVISIONE:
            raise ValueError("Nessuna proposta in revisione da confermare.")
        self.esito = self.proposta_esito
        self.stato = StatoValutazione.CONFERMATA
        self.confermata_da = incaricato
        if note:
            self.note = note
        self.save()
        self._sync_diario_stato()

    def rigetta_proposta(self, incaricato) -> None:
        """Incaricato rigetta la proposta PGV → torna IN_VALUTAZIONE sul Diario."""
        if self.stato != StatoValutazione.IN_REVISIONE:
            raise ValueError("Nessuna proposta da rigettare.")
        self.proposta_esito = None
        self.stato = StatoValutazione.ASSEGNATA
        self.save()
        self.diario.rigetta_proposta()

    def modifica(self, incaricato, esito: str, note: str = "") -> None:
        """Incaricato modifica l'esito fino alla pubblicazione (docs sez. 6 r.4)."""
        if self.pubblicata:
            raise ValueError("Non è possibile modificare un esito già pubblicato.")
        self.esito = esito
        self.stato = StatoValutazione.CONFERMATA
        self.confermata_da = incaricato
        if note:
            self.note = note
        self.save()
        self._sync_diario_stato()


class AssegnazionePGV(models.Model):
    """Assegnazione di un membro PGV a una valutazione. Vedi docs sez. 6."""

    valutazione = models.ForeignKey(
        "evaluations.Valutazione", on_delete=models.CASCADE, related_name="assegnazioni_pgv"
    )
    pgv = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="assegnazioni_ricevute",
        limit_choices_to={"ruolo": "pgv"},
    )
    assegnato_da = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="assegnazioni_fatte",
    )
    creata_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("valutazione", "pgv")]
        verbose_name = "assegnazione PGV"
        verbose_name_plural = "assegnazioni PGV"

    def __str__(self) -> str:
        return f"{self.valutazione.diario} → {self.pgv}"
