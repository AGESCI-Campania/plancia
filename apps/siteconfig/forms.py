from django import forms
from tinymce.widgets import TinyMCE

from apps.notifications.models import MailTemplate, TAG_REGISTRY
from apps.siteconfig.models import Impostazioni

_ctrl = {"class": "form-control"}
_sel = {"class": "form-select"}
_sw = {"class": "form-check-input", "role": "switch"}


class ImpostazioniForm(forms.ModelForm):
    class Meta:
        model = Impostazioni
        fields = [
            "titolo", "sottotitolo",
            "footer_testo", "footer_link_label", "footer_link_url",
            "email_mode", "from_email",
            "smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_use_tls",
            "manutenzione", "debug_toolbar", "debug_diagnostico",
        ]
        widgets = {
            "titolo": forms.TextInput(attrs=_ctrl),
            "sottotitolo": forms.TextInput(attrs=_ctrl),
            "footer_testo": forms.Textarea(attrs={**_ctrl, "rows": "3"}),
            "footer_link_label": forms.TextInput(attrs=_ctrl),
            "footer_link_url": forms.URLInput(attrs=_ctrl),
            "email_mode": forms.Select(attrs=_sel),
            "from_email": forms.EmailInput(attrs=_ctrl),
            "smtp_host": forms.TextInput(attrs=_ctrl),
            "smtp_port": forms.NumberInput(attrs=_ctrl),
            "smtp_user": forms.TextInput(attrs=_ctrl),
            "smtp_password": forms.PasswordInput(render_value=True, attrs=_ctrl),
            "smtp_use_tls": forms.CheckboxInput(attrs=_sw),
            "manutenzione": forms.CheckboxInput(attrs=_sw),
            "debug_toolbar": forms.CheckboxInput(attrs=_sw),
            "debug_diagnostico": forms.CheckboxInput(attrs=_sw),
        }


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
