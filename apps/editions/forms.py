# apps/editions/forms.py
from django import forms

from apps.editions.models import Dilazione, Edizione


class EdizioneForm(forms.ModelForm):
    class Meta:
        model = Edizione
        fields = [
            "anno", "stato",
            "scadenza_evento", "scadenza_assemblea",
            "data_evento_inizio", "data_evento_fine",
            "evento_comune", "evento_localita",
        ]
        widgets = {
            "scadenza_evento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "scadenza_assemblea": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_evento_inizio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_evento_fine": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            # hidden: valorizzato dal JS autocomplete
            "evento_comune": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        inizio = cleaned.get("data_evento_inizio")
        fine = cleaned.get("data_evento_fine")
        if inizio and fine and fine < inizio:
            self.add_error("data_evento_fine", "La data di fine non può precedere quella di inizio.")
        return cleaned


class DilazioneForm(forms.ModelForm):
    class Meta:
        model = Dilazione
        fields = ["nuova_scadenza", "motivazione"]
        widgets = {
            "nuova_scadenza": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"
            ),
            "motivazione": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
