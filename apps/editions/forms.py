# apps/editions/forms.py
"""Form di validazione di edizioni e dilazioni (usati da `services`, nessuna resa HTML)."""
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
