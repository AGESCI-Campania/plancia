from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()

# Ruoli sempre soggetti a MFA, indipendentemente dalle impostazioni.
RUOLI_MFA_SEMPRE = {"admin"}
# Ruoli soggetti a MFA solo se l'impostazione mfa_obbligatoria_ruoli_estesi è True.
RUOLI_MFA_ESTESI = {"segreteria", "incaricato_eg"}


def ruolo_richiede_mfa(user) -> bool:
    """Restituisce True se il ruolo impone la MFA.

    Admin: sempre obbligatoria.
    Segreteria e Incaricati EG: obbligatoria solo se Impostazioni.mfa_obbligatoria_ruoli_estesi=True.
    """
    ruolo = getattr(user, "ruolo", None)
    if ruolo in RUOLI_MFA_SEMPRE or getattr(user, "is_superuser", False):
        return True
    if getattr(user, "mfa_obbligatoria", False):
        return True
    if ruolo in RUOLI_MFA_ESTESI:
        try:
            from apps.siteconfig.models import Impostazioni
            return Impostazioni.get().mfa_obbligatoria_ruoli_estesi
        except Exception:
            return True  # fallback sicuro
    return False


class PlanciaAccountAdapter(DefaultAccountAdapter):
    """Oggetto email con titolo piattaforma; template da DB se disponibile."""

    _KEY_MAP = {
        "account/email/password_reset_key": "password_reset",
        "account/email/email_confirmation_signup": "email_confirmation",
        "account/email/email_confirmation": "email_confirmation",
    }

    def format_email_subject(self, subject):
        from apps.siteconfig.models import Impostazioni
        titolo = Impostazioni.get().titolo
        return f"[{titolo}] {subject}"

    def send_mail(self, template_prefix, email, context):
        from apps.notifications.models import MailTemplate, render_mail

        plancia_key = self._KEY_MAP.get(template_prefix)
        if plancia_key:
            try:
                MailTemplate.objects.get(chiave=plancia_key, attivo=True)
                plancia_ctx = self._build_context(plancia_key, context)
                oggetto, corpo_html = render_mail(plancia_key, plancia_ctx)
                from django.core.mail import EmailMultiAlternatives
                from django.utils.html import strip_tags
                msg = EmailMultiAlternatives(
                    subject=oggetto,
                    body=strip_tags(corpo_html),
                    to=[email],
                )
                msg.attach_alternative(corpo_html, "text/html")
                msg.send()
                return
            except MailTemplate.DoesNotExist:
                pass

        super().send_mail(template_prefix, email, context)

    def _build_context(self, chiave: str, allauth_ctx: dict) -> dict:
        from apps.siteconfig.models import Impostazioni
        user = allauth_ctx.get("user")
        ctx = {
            "nome": getattr(user, "first_name", "") if user else "",
            "cognome": getattr(user, "last_name", "") if user else "",
            "titolo_piattaforma": Impostazioni.get().titolo,
        }
        if chiave == "password_reset":
            ctx["link_reset"] = allauth_ctx.get("password_reset_url", "")
        elif chiave == "email_confirmation":
            ctx["link_conferma"] = allauth_ctx.get("activate_url", "") or ""
            ctx["codice"] = allauth_ctx.get("code", "") or ""
        return ctx


class PlanciaMFAAdapter(DefaultMFAAdapter):
    """Impedisce agli utenti privilegiati di disattivare il TOTP."""

    def can_delete_authenticator(self, authenticator) -> bool:
        from django.conf import settings

        if settings.DEBUG:
            return True

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
