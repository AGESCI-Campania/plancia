from django import forms
from django.forms import inlineformset_factory
from tinymce.widgets import TinyMCE

from apps.notifications.models import MailTemplate
from apps.siteconfig.models import EmailProvider, FooterLink, Impostazioni, PaginaStatica

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


class ImpostazioniForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = [
            "titolo", "sottotitolo",
            "footer_testo",
            "email_mode", "email_provider", "from_email",
            "smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_use_tls",
            "email_provider_api_key", "email_provider_webhook_secret",
            "manutenzione", "debug_toolbar", "debug_diagnostico",
        ]
        widgets = {
            "titolo": forms.TextInput(attrs=_ctrl),
            "sottotitolo": forms.TextInput(attrs=_ctrl),
            "footer_testo": _FOOTER_TINYMCE,
            "email_mode": forms.Select(attrs=_sel),
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
            "manutenzione": forms.CheckboxInput(attrs=_sw),
            "debug_toolbar": forms.CheckboxInput(attrs=_sw),
            "debug_diagnostico": forms.CheckboxInput(attrs=_sw),
        }

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance.footer_testo:
            titolo = self.instance.titolo or "Plancia"
            self.initial["footer_testo"] = (
                f"<strong>{titolo}</strong><br>Guidoncini Verdi — AGESCI Campania"
            )


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
