# apps/diaries/forms.py
from django import forms
from django.forms import inlineformset_factory

from apps.diaries.models import (
    BREVETTI_COMPETENZA,
    SPECIALITA_INDIVIDUALI,
    SPECIALITA_SQUADRIGLIA,
    Anagrafica,
    EsitoSpecialita,
    Impresa,
    MembroSq,
    Missione,
    PostoAzione,
    PostoAzioneMissione,
    Presentazione,
    RelazioneFinale,
    TipoEsito,
)


def _bootstrap(fields):
    """Aggiunge class=form-control a tutti i widget tranne checkbox."""
    for f in fields.values():
        if isinstance(f.widget, forms.CheckboxInput):
            f.widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(f.widget, (forms.Select, forms.NullBooleanSelect)):
            f.widget.attrs.setdefault("class", "form-select")
        elif isinstance(f.widget, forms.Textarea):
            f.widget.attrs.setdefault("class", "form-control")
            f.widget.attrs.setdefault("rows", 4)
        elif isinstance(f.widget, forms.HiddenInput):
            pass
        else:
            f.widget.attrs.setdefault("class", "form-control")


_SPECIALITA_SQ_CHOICES = [("", "— Scegli —")] + [(s, s) for s in SPECIALITA_SQUADRIGLIA]
_SPECIALITA_IND_CHOICES = [("", "— Scegli specialità —")] + [(s, s) for s in SPECIALITA_INDIVIDUALI]
_BREVETTI_CHOICES = [("", "— Scegli brevetto —")] + [(s, s) for s in BREVETTI_COMPETENZA]


class AnagraficaForm(forms.ModelForm):
    """Modulo 1: il CSQ/CRP editano tutto tranne crp_email (solo staff)."""

    class Meta:
        model = Anagrafica
        fields = [
            "crp_nome", "crp_cognome", "crp_email", "crp_cell",
            "specialita", "partecipa_evento",
            "desc_prima_impresa", "desc_seconda_impresa", "tecniche",
        ]
        widgets = {
            "specialita": forms.Select(choices=_SPECIALITA_SQ_CHOICES),
            "partecipa_evento": forms.CheckboxInput(),
            "desc_prima_impresa": forms.Textarea(attrs={"rows": 3}),
            "desc_seconda_impresa": forms.Textarea(attrs={"rows": 3}),
            "tecniche": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, utente=None, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)
        if utente and not utente.is_staff_plancia:
            self.fields["crp_email"].disabled = True


class PresentazioneForm(forms.ModelForm):
    class Meta:
        model = Presentazione
        fields = ["cosa_sappiamo_fare"]
        widgets = {"cosa_sappiamo_fare": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


class MembroSqForm(forms.ModelForm):
    class Meta:
        model = MembroSq
        fields = ["nome", "cognome", "ruolo", "sentiero"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


MembroSqFormSet = inlineformset_factory(
    Presentazione,
    MembroSq,
    form=MembroSqForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ImpresaForm(forms.ModelForm):
    class Meta:
        model = Impresa
        fields = ["titolo", "data_inizio", "data_fine", "perche", "come", "cosa", "link_esterno"]
        widgets = {
            "data_inizio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_fine": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "perche": forms.Textarea(attrs={"rows": 4}),
            "come": forms.Textarea(attrs={"rows": 4}),
            "cosa": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


class PostoAzioneForm(forms.ModelForm):
    class Meta:
        model = PostoAzione
        fields = ["descrizione"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


PostoAzioneFormSet = inlineformset_factory(
    Impresa, PostoAzione, form=PostoAzioneForm, extra=1, can_delete=True
)


class SpecialitaIndividualeForm(forms.ModelForm):
    """Form per una specialità individuale in un'impresa."""

    tipo = forms.CharField(widget=forms.HiddenInput(), initial=TipoEsito.SPECIALITA)

    class Meta:
        model = EsitoSpecialita
        fields = ["tipo", "nome", "stato"]
        widgets = {
            "nome": forms.Select(choices=_SPECIALITA_IND_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["tipo"].initial = TipoEsito.SPECIALITA
        _bootstrap(self.fields)


class BrevettoForm(forms.ModelForm):
    """Form per un brevetto di competenza in un'impresa."""

    tipo = forms.CharField(widget=forms.HiddenInput(), initial=TipoEsito.BREVETTO)

    class Meta:
        model = EsitoSpecialita
        fields = ["tipo", "nome", "stato"]
        widgets = {
            "nome": forms.Select(choices=_BREVETTI_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["tipo"].initial = TipoEsito.BREVETTO
        _bootstrap(self.fields)


SpecialitaFormSet = inlineformset_factory(
    Impresa, EsitoSpecialita, form=SpecialitaIndividualeForm, extra=1, can_delete=True
)

BrevettoFormSet = inlineformset_factory(
    Impresa, EsitoSpecialita, form=BrevettoForm, extra=1, can_delete=True
)


class MissioneForm(forms.ModelForm):
    class Meta:
        model = Missione
        fields = ["titolo", "data", "descrizione_svolgimento"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descrizione_svolgimento": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


class PostoAzioneMissioneForm(forms.ModelForm):
    class Meta:
        model = PostoAzioneMissione
        fields = ["descrizione"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


PostoAzioneMissioneFormSet = inlineformset_factory(
    Missione, PostoAzioneMissione, form=PostoAzioneMissioneForm, extra=1, can_delete=True
)


class RelazioneFinaleForm(forms.ModelForm):
    class Meta:
        model = RelazioneFinale
        fields = [
            "sintesi_impresa_1", "sintesi_impresa_2", "sintesi_missione",
            "considerazioni", "specialita_conquistata",
        ]
        widgets = {
            "sintesi_impresa_1": forms.Textarea(attrs={"rows": 4}),
            "sintesi_impresa_2": forms.Textarea(attrs={"rows": 4}),
            "sintesi_missione": forms.Textarea(attrs={"rows": 4}),
            "considerazioni": forms.Textarea(attrs={"rows": 5}),
            "specialita_conquistata": forms.NullBooleanSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)
