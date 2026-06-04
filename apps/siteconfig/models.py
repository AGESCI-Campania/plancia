# apps/siteconfig/models.py
from django.core.cache import cache
from django.db import models


class EmailMode(models.TextChoices):
    REALE = "reale", "Invio reale"
    SIMULATO = "simulato", "Simulato (solo log su file)"
    SIMULATO_PIU_INVIO = "simulato_piu_invio", "Simulato + invio reale"
    MAILPIT = "mailpit", "Mailpit (debug UI — /mailadmin/)"


class EmailProvider(models.TextChoices):
    SMTP = "smtp", "SMTP tradizionale"
    BREVO = "brevo", "Brevo"
    MAILGUN = "mailgun", "Mailgun"
    MAILERSEND = "mailersend", "MailerSend"
    POSTMARK = "postmark", "Postmark"
    SENDGRID = "sendgrid", "SendGrid"
    SPARKPOST = "sparkpost", "SparkPost"
    SES = "ses", "Amazon SES"


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

    # Mail — provider e modalità
    email_mode = models.CharField(
        max_length=20, choices=EmailMode.choices, default=EmailMode.SIMULATO
    )
    email_provider = models.CharField(
        max_length=20, choices=EmailProvider.choices, default=EmailProvider.SMTP,
        verbose_name="provider email",
        help_text="SMTP tradizionale oppure provider transazionale (con tracking bounce/errori).",
    )
    from_email = models.EmailField(blank=True, verbose_name="mittente (from)")
    # Impostazioni SMTP (usate solo quando email_provider = smtp)
    smtp_host = models.CharField(max_length=200, blank=True, verbose_name="SMTP host")
    smtp_port = models.PositiveIntegerField(default=587, verbose_name="SMTP porta")
    smtp_user = models.CharField(max_length=200, blank=True, verbose_name="SMTP utente")
    smtp_password = models.CharField(max_length=255, blank=True, verbose_name="SMTP password")
    smtp_use_tls = models.BooleanField(default=True, verbose_name="SMTP usa TLS")
    # Impostazioni provider transazionale (usate quando email_provider != smtp)
    email_provider_api_key = models.CharField(
        max_length=500, blank=True, verbose_name="API key provider",
        help_text="Chiave API del provider transazionale. Non usata con SMTP.",
    )
    email_provider_webhook_secret = models.CharField(
        max_length=500, blank=True, verbose_name="webhook secret",
        help_text="Secret per verificare i webhook di tracking (bounce, consegna, ecc.).",
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
    def get(cls) -> Impostazioni:
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
