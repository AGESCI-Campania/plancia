"""Ultima release GitHub nota e storico delle richieste di aggiornamento (audit trail).

Vedi `docs/piano-plancia-3.md` § "Versioni e aggiornamenti" e `docs/api/fase2-aggiornamenti.md`.
"""
from __future__ import annotations

from django.db import models


class ReleaseGitHub(models.Model):
    """Ultima release pubblicata su GitHub, aggiornata dal task `controlla_ultima_release`.

    Singleton (pk=1).
    """

    versione = models.CharField(max_length=40, blank=True, help_text="Tag, es. v2.5.0.")
    nome = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True, help_text="Note della release (markdown).")
    pubblicata_at = models.DateTimeField(null=True, blank=True)
    url = models.URLField(max_length=500, blank=True)
    controllata_at = models.DateTimeField(null=True, blank=True)
    errore = models.CharField(
        max_length=500, blank=True, help_text="Errore dell'ultimo controllo (vuoto se riuscito)."
    )

    class Meta:
        verbose_name = "ultima release GitHub"
        verbose_name_plural = "ultima release GitHub"

    def __str__(self) -> str:
        return self.versione or "(nessuna release)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls) -> ReleaseGitHub:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class StatoRichiesta(models.TextChoices):
    IN_ATTESA = "in_attesa", "In attesa"
    IN_CORSO = "in_corso", "In corso"
    COMPLETATO = "completato", "Completato"
    FALLITO = "fallito", "Fallito"
    ANNULLATO = "annullato", "Annullato"


STATI_APERTI = (StatoRichiesta.IN_ATTESA, StatoRichiesta.IN_CORSO)


class RichiestaAggiornamento(models.Model):
    """Una richiesta di aggiornamento del server fatta da un Admin dal web."""

    versione = models.CharField(max_length=40, help_text="Tag richiesto, es. v2.5.0.")
    versione_partenza = models.CharField(max_length=40, blank=True)
    richiesta_da = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="richieste_aggiornamento",
    )
    richiesta_da_email = models.CharField(max_length=254, blank=True)
    richiesta_at = models.DateTimeField(auto_now_add=True)
    stato = models.CharField(
        max_length=20, choices=StatoRichiesta.choices, default=StatoRichiesta.IN_ATTESA,
        db_index=True,
    )
    fase = models.CharField(max_length=40, blank=True)
    messaggio = models.CharField(max_length=500, blank=True)
    percentuale = models.PositiveSmallIntegerField(null=True, blank=True)
    log = models.TextField(blank=True, help_text="Ultime righe di log riportate dallo script.")
    completato_at = models.DateTimeField(null=True, blank=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-richiesta_at", "-pk"]
        verbose_name = "richiesta di aggiornamento"
        verbose_name_plural = "richieste di aggiornamento"

    def __str__(self) -> str:
        return f"#{self.pk} {self.versione} ({self.stato})"

    @property
    def aperta(self) -> bool:
        return self.stato in STATI_APERTI
