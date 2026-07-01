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


class BackendPosta(models.TextChoices):
    SMTP = "smtp", "SMTP"
    TRANSAZIONALE = "transazionale", "Provider transazionale"


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
        max_length=20,
        choices=EmailMode.choices,
        default=EmailMode.SIMULATO,
        verbose_name="Modalità invio mail",
    )
    email_provider = models.CharField(
        max_length=20,
        choices=EmailProvider.choices,
        default=EmailProvider.SMTP,
        verbose_name="provider email",
        help_text="SMTP tradizionale oppure provider transazionale (con tracking bounce/errori).",
    )
    from_name = models.CharField(max_length=100, blank=True, verbose_name="nome mittente")
    from_email = models.EmailField(blank=True, verbose_name="mittente (from)")
    # Impostazioni SMTP (usate solo quando email_provider = smtp)
    smtp_host = models.CharField(max_length=200, blank=True, verbose_name="SMTP host")
    smtp_port = models.PositiveIntegerField(default=587, verbose_name="SMTP porta")
    smtp_user = models.CharField(max_length=200, blank=True, verbose_name="SMTP utente")
    smtp_password = models.CharField(max_length=255, blank=True, verbose_name="SMTP password")
    smtp_use_tls = models.BooleanField(default=True, verbose_name="SMTP usa TLS")
    # Impostazioni provider transazionale (usate quando email_provider != smtp)
    email_provider_api_key = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="API key provider",
        help_text="Chiave API del provider transazionale. Non usata con SMTP.",
    )
    email_provider_webhook_secret = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="webhook secret",
        help_text="Secret per verificare i webhook di tracking (bounce, consegna, ecc.).",
    )
    # Routing: quale backend usare per tipo di invio
    email_backend_standard = models.CharField(
        max_length=20,
        choices=BackendPosta.choices,
        default=BackendPosta.SMTP,
        verbose_name="backend email standard",
        help_text="Backend per email di sistema (reset password, MFA, notifiche singole).",
    )
    email_backend_massivo = models.CharField(
        max_length=20,
        choices=BackendPosta.choices,
        default=BackendPosta.TRANSAZIONALE,
        verbose_name="backend invii massivi",
        help_text="Backend per inviti bulk (Capi Reparto e Capi Squadriglia).",
    )
    # Gmail OAuth per SMTP
    smtp_use_gmail_oauth = models.BooleanField(
        default=False,
        verbose_name="usa Gmail OAuth2 per SMTP",
        help_text="Se attivo, usa XOAUTH2 per smtp.gmail.com invece di username/password.",
    )
    smtp_gmail_account = models.EmailField(
        blank=True,
        verbose_name="account Gmail OAuth collegato",
    )

    # Footer
    footer_testo = models.TextField(
        blank=True,
        verbose_name="testo footer",
        help_text="Testo centrale del footer. Se vuoto usa il default.",
    )

    # Sicurezza — MFA
    # Se True: MFA obbligatoria per Admin, Segreteria e Incaricati EG.
    # Se False: obbligatoria solo per Admin (Segreteria e IABR possono accedere senza MFA).
    mfa_obbligatoria_ruoli_estesi = models.BooleanField(
        default=True,
        verbose_name="MFA obbligatoria per Segreteria e Incaricati EG",
        help_text="Se disattivato, la MFA resta obbligatoria solo per gli Admin.",
    )

    # Sicurezza — brute-force (django-axes)
    axes_failure_limit = models.PositiveIntegerField(
        default=5,
        verbose_name="tentativi prima del blocco",
        help_text="Numero di tentativi di login errati prima che l'IP venga bloccato.",
    )
    axes_cooloff_minutes = models.PositiveIntegerField(
        default=10,
        verbose_name="minuti di blocco automatico",
        help_text="Dopo quanti minuti l'IP si sblocca automaticamente. 0 = blocco permanente.",
    )
    axes_use_attempt_expiration = models.BooleanField(
        default=True,
        verbose_name="scadenza tentativi (AXES_USE_ATTEMPT_EXPIRATION)",
        help_text=(
            "Se attivo, i tentativi falliti scadono dopo il periodo di blocco e non vengono "
            "più conteggiati. Consigliato quando è impostato un blocco automatico."
        ),
    )

    # Allegati
    allegati_max_px = models.PositiveIntegerField(
        default=1024,
        verbose_name="dimensione massima immagini (px)",
        help_text=(
            "Lato maggiore in pixel delle immagini caricate come allegati. "
            "Le immagini più grandi vengono ridimensionate automaticamente al salvataggio."
        ),
    )

    # API — rate limiting
    api_ratelimit_abilitato = models.BooleanField(
        default=True,
        verbose_name="rate limiting API abilitato",
        help_text="Se attivo, limita il numero di chiamate API per utente/IP.",
    )
    api_ratelimit_per_minuto = models.PositiveIntegerField(
        default=60,
        verbose_name="max richieste al minuto (API)",
        help_text="Richieste API consentite per minuto per token/IP. 0 = illimitato.",
    )
    api_ratelimit_per_ora = models.PositiveIntegerField(
        default=1000,
        verbose_name="max richieste all'ora (API)",
        help_text="Richieste API consentite per ora per token/IP. 0 = illimitato.",
    )

    # App version control
    app_versione_minima = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="versione app minima",
        help_text="Versioni app inferiori a questa ricevono 426 e non possono accedere. Es: 2.0.0. Vuoto = nessun blocco.",
    )
    app_versione_deprecata = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="versione app deprecata (warning)",
        help_text="Versioni inferiori a questa ricevono header X-App-Upgrade-Warning ma continuano a funzionare. Es: 2.1.0.",
    )
    app_messaggio_aggiornamento = models.TextField(
        blank=True,
        default="",
        verbose_name="messaggio aggiornamento app",
        help_text="Messaggio mostrato in-app quando è disponibile un aggiornamento.",
    )
    app_funzioni_limitate = models.JSONField(
        default=list,
        blank=True,
        verbose_name="funzioni limitate per versioni deprecate",
        help_text='Lista di slug-funzione non disponibili nelle versioni deprecate. Es: ["pdf", "export_diari"].',
    )

    # Stato piattaforma / diagnostica
    manutenzione = models.BooleanField(default=False)
    debug_diagnostico = models.BooleanField(
        default=False
    )  # logging verboso (NON ribalta settings.DEBUG)
    debug_toolbar = models.BooleanField(default=False)  # visibile ai soli admin

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
        # Aggiorna la cache con l'istanza appena salvata (non solo cancella)
        # per evitare che un altro worker la riscriva subito con dati obsoleti.
        cache.set(self.CACHE_KEY, self, 300)

    @property
    def from_email_completo(self) -> str:
        """Restituisce "Nome <email>" se from_name è valorizzato, altrimenti solo l'email."""
        if self.from_name and self.from_email:
            return f"{self.from_name} <{self.from_email}>"
        return self.from_email

    @classmethod
    def get(cls) -> Impostazioni:
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj


class SlugPagina(models.TextChoices):
    PRIVACY = "privacy", "Privacy Policy"
    TERMINI = "termini", "Condizioni del Servizio"


class PaginaStatica(models.Model):
    """Pagina statica pubblica (privacy, termini). Contenuto modificabile da Admin/Segreteria/IABR."""

    slug = models.CharField(max_length=20, choices=SlugPagina.choices, unique=True)
    titolo = models.CharField(max_length=200)
    contenuto = models.TextField(blank=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pagina statica"
        verbose_name_plural = "Pagine statiche"

    def __str__(self) -> str:
        return self.get_slug_display()


class FooterLink(models.Model):
    """Uno dei link (fino a 4) mostrati nella colonna destra del footer."""

    impostazioni = models.ForeignKey(
        Impostazioni, on_delete=models.CASCADE, related_name="footer_links"
    )
    tipo = models.CharField(max_length=20, choices=TipoLink.choices, blank=True, default="")
    url = models.CharField(max_length=500, blank=True, default="", verbose_name="URL")
    etichetta = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="etichetta",
        help_text="Se vuota usa il nome del tipo (es. 'Sito web').",
    )
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "pk"]
        verbose_name = "Link footer"
        verbose_name_plural = "Link footer"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.url}"


class GmailSMTPCredenziali(models.Model):
    """Credenziali OAuth2 per Gmail SMTP (XOAUTH2). Una riga per account."""

    account_email = models.EmailField(unique=True, verbose_name="account Gmail")
    access_token = models.CharField(max_length=2000, blank=True, verbose_name="access token")
    refresh_token = models.CharField(max_length=2000, verbose_name="refresh token")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="scadenza token")
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Credenziali Gmail SMTP"
        verbose_name_plural = "Credenziali Gmail SMTP"

    def __str__(self) -> str:
        return self.account_email

    @property
    def scaduto(self) -> bool:
        from django.utils import timezone

        if not self.expires_at:
            return True
        return timezone.now() >= self.expires_at
