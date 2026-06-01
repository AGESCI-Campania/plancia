from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()

# Ruoli per cui la MFA è obbligatoria (docs sez. 2 e 12).
RUOLI_MFA_OBBLIGATORIA = {"admin", "segreteria", "incaricato_eg"}


def ruolo_richiede_mfa(user) -> bool:
    """Restituisce True se il ruolo o il flag personale impongono la MFA."""
    return (
        getattr(user, "ruolo", None) in RUOLI_MFA_OBBLIGATORIA
        or getattr(user, "mfa_obbligatoria", False)
        or getattr(user, "is_superuser", False)
    )


class PlanciaMFAAdapter(DefaultMFAAdapter):
    """Impedisce agli utenti privilegiati di disattivare il TOTP."""

    def can_delete_authenticator(self, authenticator) -> bool:
        from allauth.mfa.models import Authenticator

        user = authenticator.user
        if not ruolo_richiede_mfa(user):
            return True
        # Il TOTP non può essere rimosso; i recovery codes sì (sono rigenerabili).
        return authenticator.type != Authenticator.Type.TOTP


class PlanciaSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Blocca la creazione automatica di utenti tramite social login.

    Permette il collegamento solo se l'email del provider combacia con
    un User già esistente (creato dall'invito). Vedi docs sez. 2.
    """

    def is_auto_signup_allowed(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        """Connette silenziosamente il social account a un User esistente per email."""
        if sociallogin.is_existing:
            return
        email = sociallogin.email_addresses[0].email if sociallogin.email_addresses else None
        if not email:
            return
        try:
            user = User.objects.get(email__iexact=email)
            sociallogin.connect(request, user)
        except User.DoesNotExist:
            pass
