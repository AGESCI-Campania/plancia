"""Form di validazione delle impostazioni (usati dai servizi e dall'API, nessuna resa HTML)."""
from django import forms

from apps.notifications.models import MailTemplate
from apps.siteconfig.models import (
    EmailProvider,
    FooterLink,
    Impostazioni,
    PaginaStatica,
)

# ---------------------------------------------------------------------------
# Form per sezione — ogni sezione ha la propria form isolata
# ---------------------------------------------------------------------------

class IdentitaForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = ["titolo", "sottotitolo"]


class FooterForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = ["footer_testo"]


class EmailForm(forms.ModelForm):
    """Form per la sezione Posta elettronica.

    I campi SMTP manuali (smtp_host, smtp_port, ecc.) vengono inclusi nel salvataggio
    solo se smtp_use_gmail_oauth è False, per evitare di sovrascrivere i valori
    quando Gmail OAuth è attivo.
    """

    class Meta:
        model = Impostazioni
        fields = [
            "email_mode", "from_name", "from_email",
            "email_backend_standard", "email_backend_massivo",
            "smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_use_tls",
            "email_provider", "email_provider_api_key", "email_provider_webhook_secret",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # smtp_port è PositiveIntegerField (required=True di default) ma viene
        # nascosto nell'HTML quando Gmail OAuth è attivo. Senza required=False
        # il form fallisce silenziosamente con il campo vuoto nel POST.
        self.fields["smtp_port"].required = False

    def clean_smtp_port(self):
        # Se smtp_port arriva vuoto (campo nascosto), preserva il valore esistente
        value = self.cleaned_data.get("smtp_port")
        if value is None:
            if self.instance and self.instance.pk:
                return self.instance.smtp_port
            return 587
        return value

    def clean(self):
        cd = super().clean()
        provider = cd.get("email_provider", EmailProvider.SMTP)
        mode = cd.get("email_mode", "simulato")
        # Con Gmail OAuth attivo, smtp_host non è renderizzato nell'HTML e non è necessario
        # (Gmail OAuth sostituisce host/user/password per smtp.gmail.com).
        gmail_oauth_attivo = bool(self.instance and self.instance.smtp_use_gmail_oauth)
        if mode == "reale" and provider == EmailProvider.SMTP and not cd.get("smtp_host") and not gmail_oauth_attivo:
            self.add_error("smtp_host", "SMTP host obbligatorio per l'invio reale via SMTP.")
        if mode == "reale" and provider != EmailProvider.SMTP and not cd.get("email_provider_api_key"):
            self.add_error(
                "email_provider_api_key",
                "API key obbligatoria per l'invio reale con provider transazionale.",
            )
        return cd


# Campi SMTP manuali da escludere dal salvataggio quando Gmail OAuth è attivo
# (quei campi non vengono renderizzati nell'HTML, arriverebbero vuoti nel POST)
CAMPI_SMTP_MANUALI = frozenset({
    "smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_use_tls",
})


class SicurezzaForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = [
            "mfa_obbligatoria_ruoli_estesi",
            "axes_failure_limit", "axes_cooloff_minutes", "axes_use_attempt_expiration",
        ]


class AllegatiForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = ["allegati_max_px"]


class DiagnosticaForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = ["manutenzione", "debug_toolbar", "debug_diagnostico"]


# Mappa sezione → form class (usata da services.salva_sezione / API impostazioni)
SEZIONE_FORM: dict[str, type[forms.ModelForm]] = {
    "identita": IdentitaForm,
    "footer": FooterForm,
    "email": EmailForm,
    "sicurezza": SicurezzaForm,
    "allegati": AllegatiForm,
    "diagnostica": DiagnosticaForm,
}


# ---------------------------------------------------------------------------
# Form accessori (invariati)
# ---------------------------------------------------------------------------

class FooterLinkForm(forms.ModelForm):
    class Meta:
        model = FooterLink
        fields = ["tipo", "url", "etichetta"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].required = False
        self.fields["url"].required = False
        self.fields["etichetta"].required = False

    def clean(self):
        cd = super().clean()
        tipo = cd.get("tipo", "")
        url = cd.get("url", "").strip()
        if url and not tipo:
            cd["tipo"] = "sito_web"
        if tipo and not url:
            self.add_error("url", "Inserire l'URL per questo link.")
        return cd



class MailTemplateForm(forms.ModelForm):
    class Meta:
        model = MailTemplate
        fields = ["chiave", "oggetto", "corpo_html", "attivo"]

    def __init__(self, *args, chiave_fissa=None, **kwargs):
        super().__init__(*args, **kwargs)
        if chiave_fissa:
            self.fields["chiave"].disabled = True
            self.fields["chiave"].widget = forms.HiddenInput()
            self.initial.setdefault("chiave", chiave_fissa)
            self._chiave_fissa = chiave_fissa
        else:
            self._chiave_fissa = None

    def clean_chiave(self):
        if self._chiave_fissa:
            return self._chiave_fissa
        return self.cleaned_data["chiave"]


class PaginaStaticaForm(forms.ModelForm):
    class Meta:
        model = PaginaStatica
        fields = ["titolo", "contenuto"]
