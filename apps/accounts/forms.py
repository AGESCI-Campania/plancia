from allauth.account.forms import (
    AddEmailForm,
    ChangePasswordForm,
    LoginForm,
    ResetPasswordForm,
    SetPasswordForm,
    SignupForm,
)


class _BootstrapFormMixin:
    """Aggiunge le classi Bootstrap 5 corrette a tutti i widget del form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.forms import CheckboxInput, CheckboxSelectMultiple
        for field in self.fields.values():
            if isinstance(field.widget, (CheckboxInput, CheckboxSelectMultiple)):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class PlanciaLoginForm(_BootstrapFormMixin, LoginForm):
    """Estende il form di login per accettare email, codice socio o username.

    allauth usa EmailField per il campo 'login' in modalità email-only: lo
    sostituiamo con CharField per accettare input non-email, poi risolviamo
    codice_socio/username → email in clean_login prima che allauth faccia l'auth.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.forms import CharField, TextInput

        self.fields["login"] = CharField(
            label="Email, codice socio o username",
            widget=TextInput(attrs={
                "class": "form-control",
                "autocomplete": "username",
                "placeholder": "es. mario.rossi@email.it, 12345 o m.rossi",
            }),
        )

    def clean_login(self) -> str:
        identifier = self.cleaned_data.get("login", "").strip()
        if "@" not in identifier:
            from apps.accounts.models import User

            user: User | None = None
            if identifier.isdigit() and 4 <= len(identifier) <= 8:
                user = User.objects.filter(socio__codice_socio=identifier).first()
            if user is None:
                user = User.objects.filter(username__iexact=identifier).first()
            if user is not None:
                return user.email
        return identifier


class PlanciaSignupForm(_BootstrapFormMixin, SignupForm):
    pass


class PlanciaResetPasswordForm(_BootstrapFormMixin, ResetPasswordForm):
    pass


class PlanciaChangePasswordForm(_BootstrapFormMixin, ChangePasswordForm):
    pass


class PlanciaSetPasswordForm(_BootstrapFormMixin, SetPasswordForm):
    pass


class PlanciaAddEmailForm(_BootstrapFormMixin, AddEmailForm):
    pass
