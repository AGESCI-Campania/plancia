from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()

# Ruoli sempre soggetti a MFA, indipendentemente dalle impostazioni.
RUOLI_MFA_SEMPRE = {"admin"}
# Ruoli soggetti a MFA solo se l'impostazione mfa_obbligatoria_ruoli_estesi è True.
RUOLI_MFA_ESTESI = {"segreteria", "incaricato_eg"}

# Provider id di Sestante (SSO AGESCI Campania), uguale su tutte le piattaforme.
PROVIDER_SESTANTE = "sestante"

# Mappa dal claim Sestante al ruolo Plancia (solo ruoli globali).
_SESTANTE_CLAIM_TO_RUOLO: dict[str, str] = {
    "admin-multipiattaforma": "admin",
    "segreteria": "segreteria",
}
_RUOLI_GLOBALI: set[str] = set(_SESTANTE_CLAIM_TO_RUOLO.values())


def sessione_da_sestante(request) -> bool:
    """True se nella sessione corrente l'utente si è autenticato tramite Sestante.

    Il criterio è il metodo di autenticazione della sessione, non l'esistenza di un
    account Sestante collegato: chi ha l'account collegato ma entra con la password
    locale resta soggetto alla MFA di Plancia.
    """
    session = getattr(request, "session", None)
    if session is None:
        return False
    return any(
        m.get("method") == "socialaccount" and m.get("provider") == PROVIDER_SESTANTE
        for m in session.get("account_authentication_methods", [])
    )


def _sestante_groups(extra_data: dict) -> list[str]:
    # In allauth ≥65.11, extra_data è {"userinfo": {...}, "id_token": {...}}.
    # I claim come `groups` si trovano dentro "userinfo" (o "id_token" come fallback).
    data = extra_data.get("userinfo") or extra_data.get("id_token") or extra_data
    return data.get("groups", [])


def _sync_ruoli_globali(user, groups: list[str]) -> None:
    """Allinea i ruoli globali dell'utente al claim groups di Sestante.

    I ruoli globali (ADMIN, SEGRETERIA) arrivati da Sestante sono Nomine con
    `da_sso=True`: create se il gruppo compare nel claim, revocate (attiva=False) se
    non c'è più. Le Nomine locali, anche di Admin/Segreteria, non vengono mai toccate.
    Il ruolo attivo passa al nuovo ruolo globale se di rango maggiore; se il ruolo
    attivo era un ruolo globale revocato, torna al ruolo attivo di rango più alto
    (o a CSQ, il default della piattaforma).
    """
    from apps.accounts.models import Nomina, Ruolo
    from apps.accounts.roles import ROLE_RANK

    attesi = {_SESTANTE_CLAIM_TO_RUOLO[g] for g in groups if g in _SESTANTE_CLAIM_TO_RUOLO}
    nomine_sso = Nomina.objects.filter(utente=user, da_sso=True, attiva=True)
    nomine_sso.exclude(ruolo__in=attesi).update(attiva=False)
    gia_attivi = set(nomine_sso.values_list("ruolo", flat=True))
    nuovi = attesi - gia_attivi
    for ruolo in nuovi:
        Nomina.objects.create(utente=user, socio=user.socio, ruolo=ruolo, da_sso=True)

    # Un superutente è Admin anche senza Nomina (signal ensure_superuser_ruolo)
    disponibili = set(user.ruoli_attivi) | ({Ruolo.ADMIN} if user.is_superuser else set())
    ruolo = user.ruolo
    if nuovi:
        migliore = max(nuovi, key=lambda r: ROLE_RANK.get(r, 0))
        if ROLE_RANK.get(migliore, 0) > ROLE_RANK.get(ruolo, 0):
            ruolo = migliore
    if ruolo in _RUOLI_GLOBALI and ruolo not in disponibili:
        ruolo = max(disponibili, key=lambda r: ROLE_RANK.get(r, 0), default=Ruolo.CSQ)
    if ruolo != user.ruolo:
        User.objects.filter(pk=user.pk).update(ruolo=ruolo)
        user.ruolo = ruolo


def _rifiuta_login(request, messaggio: str):
    """Interrompe il social login con un messaggio, senza creare account parziali."""
    from allauth.core.exceptions import ImmediateHttpResponse
    from django.contrib import messages
    from django.shortcuts import redirect

    messages.error(request, messaggio)
    raise ImmediateHttpResponse(redirect("account_login"))


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

    def is_mfa_enabled(self, user, types=None) -> bool:
        # Sestante verifica già la MFA: non richiedere TOTP anche su Plancia.
        # Il bypass è attivo solo durante la pipeline di login (prima che Django
        # autentichi l'utente nella sessione), non nelle view MFA post-login.
        from allauth.core import context as allauth_context
        request = allauth_context.request
        if (
            request is not None
            and not request.user.is_authenticated
            and sessione_da_sestante(request)
        ):
            return False
        return super().is_mfa_enabled(user, types=types)


class PlanciaSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Gestisce il social login per Plancia.

    - Google/Microsoft/Apple: solo collegamento a utenti esistenti per email (nessun auto-signup).
    - Sestante (SSO AGESCI Campania): auto-provisioning consentito; sincronizzazione ruoli globali
      dal claim `groups` ad ogni login. Vedi docs/guide/sso_sestante.md.
    """

    def is_auto_signup_allowed(self, request, sociallogin):
        return sociallogin.account.provider == PROVIDER_SESTANTE

    def pre_social_login(self, request, sociallogin):
        """Collega per email gli utenti esistenti; sincronizza ruoli globali per Sestante."""
        da_sestante = sociallogin.account.provider == PROVIDER_SESTANTE
        email = sociallogin.email_addresses[0].email if sociallogin.email_addresses else None
        if da_sestante:
            if not email:
                _rifiuta_login(
                    request,
                    "Il tuo account SSO AGESCI Campania non ha un indirizzo email: "
                    "chiedi alla Segreteria regionale di aggiungerlo.",
                )
            # Sestante verifica le email dei propri utenti: senza questo allauth
            # chiederebbe una nuova conferma via email ai nuovi utenti.
            for indirizzo in sociallogin.email_addresses:
                indirizzo.verified = True

        if not sociallogin.is_existing and email:
            utenti = list(User.objects.filter(email__iexact=email)[:2])
            if len(utenti) > 1 and da_sestante:
                _rifiuta_login(
                    request,
                    f"Più account Plancia usano l'indirizzo {email}: "
                    "contatta la Segreteria regionale per unificarli.",
                )
            if len(utenti) == 1:
                sociallogin.connect(request, utenti[0])

        if da_sestante and sociallogin.is_existing:
            groups = _sestante_groups(sociallogin.account.extra_data)
            _sync_ruoli_globali(sociallogin.user, groups)

    def save_user(self, request, sociallogin, form=None):
        """Nuovi utenti da Sestante: ruoli globali dal claim groups appena creati."""
        user = super().save_user(request, sociallogin, form=form)
        if sociallogin.account.provider == PROVIDER_SESTANTE:
            _sync_ruoli_globali(user, _sestante_groups(sociallogin.account.extra_data))
        return user
