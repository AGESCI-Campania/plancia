# apps/org/models.py
from django.core.validators import RegexValidator
from django.db import models


class Zona(models.Model):
    nome = models.CharField(max_length=120, unique=True)

    def __str__(self) -> str:
        return self.nome


class Gruppo(models.Model):
    nome = models.CharField(max_length=120)
    zona = models.ForeignKey(Zona, on_delete=models.PROTECT, related_name="gruppi")

    class Meta:
        unique_together = [("nome", "zona")]

    def __str__(self) -> str:
        return f"{self.nome} ({self.zona})"


class Reparto(models.Model):
    nome = models.CharField(max_length=120)
    gruppo = models.ForeignKey(Gruppo, on_delete=models.CASCADE, related_name="reparti")

    def __str__(self) -> str:
        return f"{self.nome} - {self.gruppo}"


class Squadriglia(models.Model):
    nome = models.CharField(max_length=120)
    reparto = models.ForeignKey(Reparto, on_delete=models.CASCADE, related_name="squadriglie")

    def __str__(self) -> str:
        return f"{self.nome} - {self.reparto}"


class Categoria(models.TextChoices):
    CAPO = "capo", "Capo"        # da Co.Ca.: tutti i ruoli tranne CSQ
    RAGAZZO = "ragazzo", "Ragazzo"  # da tracciato ragazzi: solo CSQ


codice_socio_validator = RegexValidator(
    r"^[0-9]{4,8}$", "Il codice socio deve essere numerico, da 4 a 8 cifre."
)


class Socio(models.Model):
    """Anagrafica persone (capi e ragazzi). Vedi docs sez. 14.

    Il codice socio e' l'identificativo univoco di piattaforma.
    Da Socio si selezionano i ruoli (capo -> tutti tranne CSQ; ragazzo -> solo CSQ).
    """

    codice_socio = models.CharField(
        max_length=8, unique=True, validators=[codice_socio_validator],
        help_text="Solo numerico, 4-8 cifre.",
    )
    nome = models.CharField(max_length=120)
    cognome = models.CharField(max_length=120)
    email = models.EmailField(blank=True)  # i ragazzi nascono senza email (aggiunta da import Evento)
    categoria = models.CharField(max_length=10, choices=Categoria.choices)

    gruppo = models.ForeignKey(Gruppo, on_delete=models.PROTECT, related_name="soci")
    zona = models.ForeignKey(Zona, on_delete=models.PROTECT, related_name="soci")

    # accessori opzionali da import
    cellulare = models.CharField(max_length=30, blank=True)
    branca = models.CharField(max_length=40, blank=True)
    sesso = models.CharField(max_length=1, blank=True)
    data_nascita = models.DateField(null=True, blank=True)
    livello_foca = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=60, blank=True)

    class Meta:
        indexes = [models.Index(fields=["cognome", "nome"])]

    def __str__(self) -> str:
        return f"{self.cognome} {self.nome} - {self.gruppo} (#{self.codice_socio})"

    @property
    def email_modificabile_dall_interessato(self) -> bool:
        """L'email del capo NON e' modificabile dal capo; quella del ragazzo si'."""
        return self.categoria == Categoria.RAGAZZO

    # TODO (Claude Code): Zona/Gruppo/Reparto/Squadriglia vanno completati con i campi
    # accessori; il legame Socio<->User (OneToOne) si crea all'attivazione account.
