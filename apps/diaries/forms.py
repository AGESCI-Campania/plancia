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
    TipoDiario,
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
    """Modulo 1: dati Capo Reparto, Capo Squadriglia, specialità e precompilazione."""

    squadriglia_nome = forms.CharField(
        max_length=120,
        label="Nome squadriglia",
        help_text="Modifica il nome della squadriglia. Rinominerà anche le cartelle su Google Drive.",
        widget=forms.TextInput(attrs={"placeholder": "es. Pantere"}),
    )
    tipo_diario = forms.ChoiceField(
        choices=TipoDiario.choices,
        label="Tipo partecipazione",
        help_text="Nuovo: la squadriglia partecipa per la prima volta. Rinnovo: ha già conquistato la specialità.",
    )

    class Meta:
        model = Anagrafica
        fields = [
            "crp_cognome", "crp_nome", "crp_email", "crp_cell",
            "csq_cognome", "csq_nome", "csq_email", "csq_cell",
            "specialita", "partecipa_evento",
            "desc_prima_impresa", "desc_seconda_impresa", "tecniche",
        ]
        widgets = {
            "specialita": forms.Select(choices=_SPECIALITA_SQ_CHOICES),
            "partecipa_evento": forms.CheckboxInput(),
            "crp_nome": forms.TextInput(attrs={"placeholder": "Nome"}),
            "crp_cognome": forms.TextInput(attrs={"placeholder": "Cognome"}),
            "crp_email": forms.EmailInput(attrs={"placeholder": "email@esempio.it"}),
            "crp_cell": forms.TextInput(attrs={"placeholder": "3xx xxxxxxx"}),
            "csq_nome": forms.TextInput(attrs={"placeholder": "Nome"}),
            "csq_cognome": forms.TextInput(attrs={"placeholder": "Cognome"}),
            "csq_email": forms.EmailInput(attrs={"placeholder": "email@esempio.it"}),
            "csq_cell": forms.TextInput(attrs={"placeholder": "3xx xxxxxxx"}),
            "desc_prima_impresa": forms.Textarea(attrs={"rows": 3}),
            "desc_seconda_impresa": forms.Textarea(attrs={"rows": 3}),
            "tecniche": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, utente=None, diario=None, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)
        # Email editabile solo da staff
        if utente and not utente.is_staff_plancia:
            self.fields["crp_email"].disabled = True
            self.fields["csq_email"].disabled = True
        # Note da import: sempre non editabili
        for f in ("desc_prima_impresa", "desc_seconda_impresa", "tecniche"):
            self.fields[f].disabled = True
            self.fields[f].widget.attrs["readonly"] = True
        # Valore iniziale tipo e squadriglia
        if diario and "squadriglia_nome" not in self.initial:
            self.initial["squadriglia_nome"] = diario.squadriglia.nome
        if diario and "tipo_diario" not in self.initial:
            self.initial["tipo_diario"] = diario.tipo
        _bootstrap({"squadriglia_nome": self.fields["squadriglia_nome"],
                    "tipo_diario": self.fields["tipo_diario"]})


class PresentazioneForm(forms.ModelForm):
    class Meta:
        model = Presentazione
        fields = ["cosa_sappiamo_fare"]
        widgets = {
            "cosa_sappiamo_fare": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "Descrivete le competenze e le attività che la vostra squadriglia sa fare meglio...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


class MembroSqForm(forms.ModelForm):
    class Meta:
        model = MembroSq
        fields = ["nome", "ruolo", "sentiero"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome e cognome"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


MembroSqFormSet = inlineformset_factory(
    Presentazione,
    MembroSq,
    form=MembroSqForm,
    extra=3,
    can_delete=True,
    min_num=0,
)


class ImpresaForm(forms.ModelForm):
    class Meta:
        model = Impresa
        fields = ["titolo", "data_inizio", "data_fine", "perche", "come", "cosa", "link_esterno"]
        widgets = {
            "titolo": forms.TextInput(attrs={"placeholder": "Titolo dell'impresa"}),
            "data_inizio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_fine": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "perche": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Descriveteci perché avete deciso di fare questa impresa: cosa vi piaceva, cosa vi ha spinto a farla, ecc.",
            }),
            "come": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Come avete progettato il vostro lavoro, come avete acquisito le competenze necessarie e quali sono, come vi siete divisi i posti d'azione in squadriglia, ecc.",
            }),
            "cosa": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Quello che avete fatto per realizzare l'impresa, dove l'avete realizzata e tutte le informazioni utili per poterci far comprendere il vostro lavoro.",
            }),
            "link_esterno": forms.URLInput(attrs={
                "placeholder": "https://youtube.com/...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)


class PostoAzioneForm(forms.ModelForm):
    class Meta:
        model = PostoAzione
        fields = ["chi", "cosa"]
        widgets = {
            "chi": forms.TextInput(attrs={"placeholder": "Nome (es. Mario Rossi)"}),
            "cosa": forms.TextInput(attrs={"placeholder": "Posto d'azione (es. Fotografia)"}),
        }

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
        fields = ["tipo", "chi", "nome", "stato"]
        widgets = {
            "nome": forms.Select(choices=_SPECIALITA_IND_CHOICES),
            "chi": forms.TextInput(attrs={"placeholder": "Nome del membro"}),
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
        fields = ["tipo", "chi", "nome", "stato"]
        widgets = {
            "nome": forms.Select(choices=_BREVETTI_CHOICES),
            "chi": forms.TextInput(attrs={"placeholder": "Nome del membro"}),
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
            "titolo": forms.TextInput(attrs={"placeholder": "Titolo della missione"}),
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descrizione_svolgimento": forms.Textarea(attrs={
                "rows": 6,
                "placeholder": (
                    "Descrizione e svolgimento della Missione; che obiettivi vi sono stati dati; "
                    "quali le tecniche usate; quali competenze ha richiesto la missione e come vi "
                    "siete divisi i posti d'azione; eventuali problemi, ecc."
                ),
            }),
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
            "sintesi_impresa_1": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": (
                    "Sintesi del percorso fatto dalla Squadriglia durante la prima impresa "
                    "(oggetto, tempi, luoghi, cambiamenti che ti aspettavi in fase progettuale, "
                    "obiettivi raggiunti, eventuali problematiche)."
                ),
            }),
            "sintesi_impresa_2": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": (
                    "Sintesi del percorso fatto dalla Squadriglia durante la seconda impresa "
                    "(oggetto, tempi, luoghi, cambiamenti che ti aspettavi in fase progettuale, "
                    "obiettivi raggiunti, eventuali problematiche)."
                ),
            }),
            "sintesi_missione": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": (
                    "Sintesi del percorso fatto dalla Squadriglia durante la missione "
                    "(obiettivi, tempi, luoghi, cambiamenti, obiettivi raggiunti, eventuali problematiche)."
                ),
            }),
            "considerazioni": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": (
                    "Alla fine del percorso verso la specialità, le competenze acquisite hanno avuto "
                    "una ricaduta concreta nella vita di squadriglia/reparto o sono rimaste fini a se stesse? "
                    "Nella conquista della specialità, i membri della squadriglia hanno acquisito "
                    "specialità individuali/brevetti di competenza?"
                ),
            }),
            "specialita_conquistata": forms.NullBooleanSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["specialita_conquistata"].label = (
            "Ritieni che la specialità di squadriglia sia stata conquistata?"
        )
        _bootstrap(self.fields)
