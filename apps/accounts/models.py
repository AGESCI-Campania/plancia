# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class Ruolo(models.TextChoices):
    ADMIN = "admin", "Admin"
    SEGRETERIA = "segreteria", "Segreteria regionale"
    INCARICATO_EG = "incaricato_eg", "Incaricato EG (IABR EG)"
    PGV = "pgv", "Membro Pattuglia Guidoncini Verdi"
    CRP = "crp", "Capo Reparto"
    CSQ = "csq", "Capo Squadriglia"


class User(AbstractUser):
    """Utente custom. AUTH_USER_MODEL non è modificabile dopo la prima migrazione.

    Il campo `socio` collega l'account all'anagrafica (1:1); null=True perché
    gli Admin possono non avere un Socio associato. Vedi docs sez. 2.
    """

    email = models.EmailField("indirizzo email", unique=True)
    ruolo = models.CharField(max_length=20, choices=Ruolo.choices, default=Ruolo.CSQ)
    mfa_obbligatoria = models.BooleanField(default=False)
    socio = models.OneToOneField(
        "org.Socio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="utente",
        verbose_name="socio collegato",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self) -> str:
        return self.email or self.username

    @property
    def nome_completo(self) -> str:
        if self.socio:
            return f"{self.socio.cognome} {self.socio.nome}"
        return self.get_full_name() or self.email

    def ha_ruolo(self, *ruoli: str) -> bool:
        return self.ruolo in ruoli

    @property
    def is_staff_plancia(self) -> bool:
        """Admin, Segreteria e Incaricati EG: gestiscono la piattaforma."""
        return self.ruolo in (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)


class Nomina(models.Model):
    """Traccia l'assegnazione di un ruolo a una persona (audit). Vedi docs sez. 2."""

    socio = models.ForeignKey(
        "org.Socio", on_delete=models.CASCADE, related_name="nomine", null=True, blank=True
    )
    utente = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="nomine", null=True, blank=True
    )
    ruolo = models.CharField(max_length=20, choices=Ruolo.choices)
    nominato_da = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="nomine_effettuate"
    )
    edizione = models.ForeignKey(
        "editions.Edizione",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="nomine",
        help_text="Valorizzato solo per i ruoli contestuali CRP/CSQ.",
    )
    creato_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.ruolo} → {self.socio or self.utente}"


class EsitoLogin(models.TextChoices):
    OK = "login", "Login riuscito"
    LOGOUT = "logout", "Logout"
    FALLITO = "fallito", "Tentativo fallito"


class LoginEvent(models.Model):
    """Audit delle sessioni di accesso (docs sez. 12).

    Alimentato dai signal di django-allauth in apps/accounts/apps.py.
    """

    utente = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="login_events",
        null=True,
        blank=True,
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    provider = models.CharField(max_length=50, blank=True, help_text="vuoto=email; google/microsoft/apple")
    esito = models.CharField(max_length=10, choices=EsitoLogin.choices)
    creato_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creato_at"]
        verbose_name = "evento di login"
        verbose_name_plural = "eventi di login"

    def __str__(self) -> str:
        return f"{self.esito} {self.utente} {self.creato_at:%Y-%m-%d %H:%M}"
