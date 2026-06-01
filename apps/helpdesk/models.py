# apps/helpdesk/models.py
from django.db import models
from django.utils import timezone


class CategoriaTicket(models.TextChoices):
    TECNICO = "tecnico", "Problema tecnico"
    COMPILAZIONE = "compilazione", "Difficoltà di compilazione"
    ACCESSO = "accesso", "Problema di accesso"
    DILAZIONE = "dilazione", "Richiesta dilazione"
    ALTRO = "altro", "Altro"


class StatoTicket(models.TextChoices):
    APERTO = "aperto", "Aperto"
    IN_LAVORAZIONE = "in_lavorazione", "In lavorazione"
    CHIUSO = "chiuso", "Chiuso"


class Ticket(models.Model):
    """Ticket helpdesk aperto da CRP/CSQ verso segreteria/incaricati. Vedi docs sez. 13."""

    aperto_da = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="ticket_aperti"
    )
    diario = models.ForeignKey(
        "diaries.Diario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket",
    )
    oggetto = models.CharField(max_length=200)
    corpo = models.TextField()
    categoria = models.CharField(max_length=20, choices=CategoriaTicket.choices)
    stato = models.CharField(
        max_length=20, choices=StatoTicket.choices, default=StatoTicket.APERTO, db_index=True
    )
    assegnato_a = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_assegnati",
    )
    chiuso_at = models.DateTimeField(null=True, blank=True)
    creato_at = models.DateTimeField(auto_now_add=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creato_at"]
        verbose_name = "ticket"
        verbose_name_plural = "ticket"

    def __str__(self) -> str:
        return f"#{self.pk} {self.oggetto} ({self.stato})"

    def get_absolute_url(self) -> str:
        from django.urls import reverse
        return reverse("helpdesk:detail", kwargs={"pk": self.pk})

    def chiudi(self, operatore) -> None:
        self.stato = StatoTicket.CHIUSO
        self.chiuso_at = timezone.now()
        self.assegnato_a = operatore
        self.save(update_fields=["stato", "chiuso_at", "assegnato_a"])

    def prendi_in_carico(self, operatore) -> None:
        self.stato = StatoTicket.IN_LAVORAZIONE
        self.assegnato_a = operatore
        self.save(update_fields=["stato", "assegnato_a"])


class RispostaTicket(models.Model):
    """Messaggio di risposta/aggiornamento su un ticket."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="risposte")
    autore = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="risposte_ticket"
    )
    testo = models.TextField()
    creata_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creata_at"]
        verbose_name = "risposta"
        verbose_name_plural = "risposte"

    def __str__(self) -> str:
        return f"Risposta {self.ticket} da {self.autore}"
