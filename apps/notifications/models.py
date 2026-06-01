# apps/notifications/models.py
import uuid

from django.db import models

from apps.accounts.models import Ruolo

# Registro dei tag ammessi per ciascun template (docs sez. 15).
TAG_REGISTRY: dict[str, list[str]] = {
    "invito_csq": ["nome", "cognome", "titolo_piattaforma", "link_attivazione",
                   "edizione", "squadriglia", "scadenza"],
    "invito_crp": ["nome", "cognome", "titolo_piattaforma", "link_attivazione",
                   "edizione", "reparto", "scadenza"],
    "invito_pgv": ["nome", "cognome", "titolo_piattaforma", "link_attivazione", "edizione"],
    "esito_pubblicato": ["nome", "cognome", "titolo_piattaforma", "squadriglia", "esito", "note"],
    "dilazione": ["nome", "cognome", "titolo_piattaforma", "squadriglia",
                  "nuova_scadenza", "motivazione"],
    "richiesta_info": ["nome", "cognome", "titolo_piattaforma", "squadriglia", "note"],
    # Email di sistema (allauth) — personalizzabili da impostazioni
    "password_reset": ["nome", "cognome", "titolo_piattaforma", "link_reset"],
    "email_confirmation": ["nome", "cognome", "titolo_piattaforma", "link_conferma", "codice"],
}


class MailTemplate(models.Model):
    """Template email modificabile da Impostazioni (rich text). Vedi docs sez. 15."""

    chiave = models.CharField(max_length=40, unique=True, choices=[(k, k) for k in TAG_REGISTRY])
    oggetto = models.CharField(max_length=255)
    corpo_html = models.TextField(help_text="HTML rich text. Usa i tag {{ ... }} disponibili.")
    attivo = models.BooleanField(default=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "template email"
        verbose_name_plural = "template email"

    def __str__(self) -> str:
        return self.chiave

    @property
    def tag_disponibili(self) -> list[str]:
        return TAG_REGISTRY.get(self.chiave, [])


def render_mail(chiave: str, context: dict) -> tuple[str, str]:
    """Rende (oggetto, corpo_html) applicando SOLO i tag previsti per la chiave.

    Se il template non esiste in DB, usa il fallback da file (templates/mail/<chiave>.html).
    """
    from django.template import Context, Template
    from django.template.loader import render_to_string

    try:
        tpl = MailTemplate.objects.get(chiave=chiave, attivo=True)
        allowed = {k: context.get(k, "") for k in TAG_REGISTRY.get(chiave, [])}
        oggetto = Template(tpl.oggetto).render(Context(allowed))
        corpo = Template(tpl.corpo_html).render(Context(allowed))
    except MailTemplate.DoesNotExist:
        allowed = {k: context.get(k, "") for k in TAG_REGISTRY.get(chiave, [])}
        oggetto = context.get("titolo_piattaforma", "Plancia")
        corpo = render_to_string(f"mail/{chiave}.html", allowed)
    return oggetto, corpo


# ---------------------------------------------------------------------------
# Inviti
# ---------------------------------------------------------------------------

class StatoInvito(models.TextChoices):
    INVIATO = "inviato", "Inviato"
    ATTIVATO = "attivato", "Attivato"
    SCADUTO = "scaduto", "Scaduto"


class Invito(models.Model):
    """Invito con token per attivare l'account di CSQ, CRP o PGV. Vedi docs sez. 8."""

    diario = models.ForeignKey(
        "diaries.Diario",
        on_delete=models.CASCADE,
        related_name="inviti",
        null=True, blank=True,
    )
    utente = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="inviti_ricevuti"
    )
    ruolo_target = models.CharField(max_length=20, choices=Ruolo.choices)
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    stato = models.CharField(
        max_length=10, choices=StatoInvito.choices, default=StatoInvito.INVIATO
    )
    inviato_at = models.DateTimeField(auto_now_add=True)
    attivato_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-inviato_at"]
        verbose_name = "invito"
        verbose_name_plural = "inviti"

    def __str__(self) -> str:
        return f"Invito {self.ruolo_target} → {self.utente} ({self.stato})"

    def attiva(self) -> None:
        from django.utils import timezone
        self.stato = StatoInvito.ATTIVATO
        self.attivato_at = timezone.now()
        self.save(update_fields=["stato", "attivato_at"])
