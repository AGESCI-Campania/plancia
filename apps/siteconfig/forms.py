from django import forms
from django.forms import inlineformset_factory
from tinymce.widgets import TinyMCE

from apps.notifications.models import MailTemplate
from apps.siteconfig.models import (
    EmailProvider,
    FooterLink,
    Impostazioni,
    PaginaStatica,
)

_ctrl = {"class": "form-control"}
_sel = {"class": "form-select"}
_sw = {"class": "form-check-input", "role": "switch"}

_FOOTER_TINYMCE = TinyMCE(
    attrs={"rows": 5},
    mce_attrs={
        "toolbar": "bold italic | link | code",
        "height": 140,
        "menubar": False,
    },
)


# ---------------------------------------------------------------------------
# Form per sezione — ogni sezione ha la propria form isolata
# ---------------------------------------------------------------------------

class IdentitaForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = ["titolo", "sottotitolo"]
        widgets = {
            "titolo": forms.TextInput(attrs=_ctrl),
            "sottotitolo": forms.TextInput(attrs=_ctrl),
        }


class FooterForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = ["footer_testo"]
        widgets = {"footer_testo": _FOOTER_TINYMCE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance.footer_testo:
            titolo = self.instance.titolo or "Plancia"
            self.initial["footer_testo"] = (
                f"<strong>{titolo}</strong><br>Guidoncini Verdi — AGESCI Campania"
            )


class EmailForm(forms.ModelForm):
    """Form per la sezione Posta elettronica.

    I campi SMTP manuali (smtp_host, smtp_port, ecc.) vengono inclusi nel salvataggio
    solo se smtp_use_gmail_oauth è False, per evitare di sovrascrivere i valori
    quando quei campi non sono renderizzati nell'HTML.
    """

    class Meta:
        model = Impostazioni
        fields = [
            "email_mode", "from_email",
            "email_backend_standard", "email_backend_massivo",
            "smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_use_tls",
            "email_provider", "email_provider_api_key", "email_provider_webhook_secret",
        ]
        widgets = {
            "email_mode": forms.Select(attrs=_sel),
            "email_backend_standard": forms.Select(attrs=_sel),
            "email_backend_massivo": forms.Select(attrs=_sel),
            "email_provider": forms.Select(attrs=_sel),
            "from_email": forms.EmailInput(attrs=_ctrl),
            "smtp_host": forms.TextInput(attrs=_ctrl),
            "smtp_port": forms.NumberInput(attrs=_ctrl),
            "smtp_user": forms.TextInput(attrs=_ctrl),
            "smtp_password": forms.PasswordInput(render_value=True, attrs=_ctrl),
            "smtp_use_tls": forms.CheckboxInput(attrs=_sw),
            "email_provider_api_key": forms.PasswordInput(
                render_value=True,
                attrs={**_ctrl, "autocomplete": "off"},
            ),
            "email_provider_webhook_secret": forms.PasswordInput(
                render_value=True,
                attrs={**_ctrl, "autocomplete": "off"},
            ),
        }

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
        if mode == "reale" and provider == EmailProvider.SMTP and not cd.get("smtp_host"):
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
        widgets = {
            "mfa_obbligatoria_ruoli_estesi": forms.CheckboxInput(attrs=_sw),
            "axes_failure_limit": forms.NumberInput(attrs={**_ctrl, "min": "1", "max": "20"}),
            "axes_cooloff_minutes": forms.NumberInput(attrs={**_ctrl, "min": "0", "max": "1440"}),
            "axes_use_attempt_expiration": forms.CheckboxInput(attrs=_sw),
        }


class AllegatiForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = ["allegati_max_px"]
        widgets = {
            "allegati_max_px": forms.NumberInput(attrs={**_ctrl, "min": "256", "max": "4096"}),
        }


class DiagnosticaForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = ["manutenzione", "debug_toolbar", "debug_diagnostico"]
        widgets = {
            "manutenzione": forms.CheckboxInput(attrs=_sw),
            "debug_toolbar": forms.CheckboxInput(attrs=_sw),
            "debug_diagnostico": forms.CheckboxInput(attrs=_sw),
        }


# Mappa sezione → form class (usata dalla view)
SEZIONE_FORM: dict[str, type[forms.ModelForm]] = {
    "identita": IdentitaForm,
    "footer": FooterForm,
    "email": EmailForm,
    "sicurezza": SicurezzaForm,
    "allegati": AllegatiForm,
    "diagnostica": DiagnosticaForm,
}

SEZIONE_LABEL: dict[str, str] = {
    "identita": "Identità",
    "footer": "Footer",
    "email": "Posta elettronica",
    "sicurezza": "Sicurezza",
    "allegati": "Allegati",
    "diagnostica": "Diagnostica",
}


# ---------------------------------------------------------------------------
# Form accessori (invariati)
# ---------------------------------------------------------------------------

class FooterLinkForm(forms.ModelForm):
    class Meta:
        model = FooterLink
        fields = ["tipo", "url", "etichetta"]
        widgets = {
            "tipo": forms.Select(attrs=_sel),
            "url": forms.TextInput(attrs={**_ctrl, "placeholder": "https://... oppure mailto:..."}),
            "etichetta": forms.TextInput(attrs={**_ctrl, "placeholder": "es. Seguici", "maxlength": "20"}),
        }

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


FooterLinkFormSet = inlineformset_factory(
    Impostazioni,
    FooterLink,
    form=FooterLinkForm,
    extra=5,
    max_num=5,
    can_delete=True,
)


class MailTemplateForm(forms.ModelForm):
    class Meta:
        model = MailTemplate
        fields = ["chiave", "oggetto", "corpo_html", "attivo"]
        widgets = {
            "chiave": forms.Select(attrs={**_sel, "class": "form-select"}),
            "oggetto": forms.TextInput(attrs=_ctrl),
            "corpo_html": TinyMCE(attrs={"rows": 20}),
            "attivo": forms.CheckboxInput(attrs=_sw),
        }

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
        widgets = {
            "titolo": forms.TextInput(attrs=_ctrl),
            "contenuto": TinyMCE(
                attrs={"rows": 30},
                mce_attrs={
                    "toolbar": (
                        "bold italic underline | bullist numlist | "
                        "link | h2 h3 | removeformat | code"
                    ),
                    "height": 500,
                    "menubar": False,
                },
            ),
        }
