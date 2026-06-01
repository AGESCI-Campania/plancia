# apps/siteconfig/models.py
from django.core.cache import cache
from django.db import models


class EmailMode(models.TextChoices):
    REALE = "reale", "Invio reale (SMTP)"
    SIMULATO = "simulato", "Simulato (solo log su file)"
    SIMULATO_PIU_INVIO = "simulato_piu_invio", "Simulato + invio reale"


class TipoLink(models.TextChoices):
    SITO_WEB = "sito_web", "Sito web"
    EMAIL = "email", "Email"
    FACEBOOK = "facebook", "Facebook"
    INSTAGRAM = "instagram", "Instagram"
    TIKTOK = "tiktok", "TikTok"


class Impostazioni(models.Model):
    """Configurazione di piattaforma. Singleton: esiste una sola riga (pk=1).
    Modificabile SOLO dagli amministratori. Vedi docs sez. 15.
    """

    titolo = models.CharField(max_length=120, default="Plancia")
    sottotitolo = models.CharField(
        max_length=200, default="Guidoncini Verdi - AGESCI Campania", blank=True
    )

    # Mail (SMTP) - la password va cifrata a riposo (TODO: campo cifrato)
    smtp_host = models.CharField(max_length=200, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=200, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    from_email = models.EmailField(blank=True)
    email_mode = models.CharField(
        max_length=20, choices=EmailMode.choices, default=EmailMode.SIMULATO
    )

    # Footer
    footer_testo = models.TextField(
        blank=True, verbose_name="testo footer",
        help_text="Testo centrale del footer. Se vuoto usa il default.",
    )

    # Stato piattaforma / diagnostica
    manutenzione = models.BooleanField(default=False)
    debug_diagnostico = models.BooleanField(default=False)  # logging verboso (NON ribalta settings.DEBUG)
    debug_toolbar = models.BooleanField(default=False)      # visibile ai soli admin

    aggiornato_at = models.DateTimeField(auto_now=True)

    CACHE_KEY = "plancia:impostazioni"

    class Meta:
        verbose_name = "Impostazioni"
        verbose_name_plural = "Impostazioni"

    def __str__(self) -> str:
        return self.titolo

    def save(self, *args, **kwargs):
        self.pk = 1  # forza il singleton
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @classmethod
    def get(cls) -> "Impostazioni":
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj


class FooterLink(models.Model):
    """Uno dei link (fino a 5) mostrati nella colonna destra del footer."""

    impostazioni = models.ForeignKey(
        Impostazioni, on_delete=models.CASCADE, related_name="footer_links"
    )
    tipo = models.CharField(max_length=20, choices=TipoLink.choices, blank=True, default="")
    url = models.CharField(max_length=500, blank=True, default="", verbose_name="URL")
    etichetta = models.CharField(
        max_length=20, blank=True, default="", verbose_name="etichetta",
        help_text="Se vuota usa il nome del tipo (es. 'Sito web').",
    )
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "pk"]
        verbose_name = "Link footer"
        verbose_name_plural = "Link footer"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.url}"
