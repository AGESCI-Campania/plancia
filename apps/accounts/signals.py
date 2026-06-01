# apps/accounts/signals.py
"""Registra LoginEvent dai signal di django-allauth (docs sez. 12)."""
from allauth.account.signals import user_logged_in, user_logged_out
from django.contrib.auth.signals import user_login_failed as auth_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver


def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@receiver(post_save, sender="accounts.User")
def ensure_superuser_ruolo(sender, instance, **kwargs):
    """I superutenti devono avere ruolo Admin; corregge il default CSQ di createsuperuser."""
    from apps.accounts.models import Ruolo
    if instance.is_superuser and instance.ruolo != Ruolo.ADMIN:
        sender.objects.filter(pk=instance.pk).update(ruolo=Ruolo.ADMIN)


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    from apps.accounts.models import EsitoLogin, LoginEvent

    LoginEvent.objects.create(
        utente=user,
        ip=_get_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        provider=getattr(getattr(request, "socialaccount_last_login", None), "provider", ""),
        esito=EsitoLogin.OK,
    )


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    from apps.accounts.models import EsitoLogin, LoginEvent

    if user:
        LoginEvent.objects.create(
            utente=user,
            ip=_get_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            esito=EsitoLogin.LOGOUT,
        )


@receiver(auth_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    from apps.accounts.models import EsitoLogin, LoginEvent
    from apps.accounts.models import User

    email = credentials.get("email") or credentials.get("username", "")
    utente = User.objects.filter(email=email).first()
    LoginEvent.objects.create(
        utente=utente,
        ip=_get_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        esito=EsitoLogin.FALLITO,
    )
