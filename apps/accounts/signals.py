# apps/accounts/signals.py
"""Registra LoginEvent dai signal di django-allauth (docs sez. 12)."""
import ipaddress

from allauth.account.signals import user_logged_in, user_logged_out
from django.contrib.auth.signals import user_login_failed as auth_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver


def _get_ip(request) -> str | None:
    """Estrae e valida l'IP del client; restituisce None se non ricavabile."""
    candidates: list[str] = []
    for header in ("HTTP_X_FORWARDED_FOR", "HTTP_X_REAL_IP", "REMOTE_ADDR"):
        value = request.META.get(header, "") or ""
        candidates.extend(part.strip() for part in value.split(",") if part.strip())
    for addr in candidates:
        try:
            ipaddress.ip_address(addr)
            return addr
        except ValueError:
            continue
    return None


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
    from apps.accounts.models import EsitoLogin, LoginEvent, User

    email = credentials.get("email") or credentials.get("username", "")
    utente = User.objects.filter(email=email).first()
    LoginEvent.objects.create(
        utente=utente,
        ip=_get_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        esito=EsitoLogin.FALLITO,
    )
