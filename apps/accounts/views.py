# apps/accounts/views.py
from allauth.account.views import PasswordChangeView as AllauthPasswordChangeView
from allauth.mfa.base.views import AuthenticateView as MFAAuthenticateView
from allauth.mfa.models import Authenticator
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts import services
from apps.accounts.mixins import StaffPlanciaRequiredMixin
from apps.accounts.models import Ruolo, User
from apps.accounts.roles import nomina as service_nomina


def _primo_messaggio(exc: ValidationError) -> str:
    return next(iter(exc.messages), "Dati non validi.")


class PlanciaAuthenticateView(MFAAuthenticateView):
    """Sovrascrive AuthenticateView per evitare begin_authentication() inutile.

    Senza override, allauth chiama begin_authentication() e scrive stato WebAuthn
    in sessione a ogni GET della pagina TOTP, anche per utenti senza passkey.
    Su iOS Safari dopo redirect OAuth cross-site questo causa errori CSRF.
    """

    def _build_forms(self):
        result = super()._build_forms()
        user = self.stage.login.user
        if self.webauthn_form is not None:
            if not Authenticator.objects.filter(
                user=user, type=Authenticator.Type.WEBAUTHN
            ).exists():
                self.webauthn_form = None
        return result


class ProfiloView(LoginRequiredMixin, TemplateView):
    """Profilo dell'utente corrente. Email editabile solo dai CSQ (ragazzi)."""

    template_name = "accounts/profilo.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_items"] = [{"label": "Home", "url": "/"}, {"label": "Profilo", "url": None}]
        u = self.request.user
        ctx["nomine"] = u.nomine.select_related("nominato_da", "edizione").order_by("-creato_at")
        ctx["login_events"] = u.login_events.all()[:10]
        ctx["puo_modificare_email"] = services.puo_modificare_email(u)
        from allauth.socialaccount.models import SocialAccount
        ctx["social_accounts"] = SocialAccount.objects.filter(user=u)
        return ctx

    def post(self, request):
        """Aggiornamento email per i CSQ."""
        try:
            services.aggiorna_email(request.user, request.POST.get("email", ""))
        except ValidationError as exc:
            messages.error(request, _primo_messaggio(exc))
            return redirect("accounts:profilo")
        messages.success(request, "Email aggiornata.")
        return redirect("accounts:profilo")


class UtenteListView(StaffPlanciaRequiredMixin, ListView):
    """Lista utenti — Admin, Segreteria, Incaricato EG."""

    model = User
    template_name = "accounts/utente_list.html"
    context_object_name = "utenti"
    paginate_by = 50

    def get_queryset(self):
        return services.utenti_filtrati(self.request.GET.get("ruolo"), self.request.GET.get("q"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_items"] = [{"label": "Home", "url": "/"}, {"label": "Utenti", "url": None}]
        ctx["ruoli"] = Ruolo.choices
        ctx["ruolo_sel"] = self.request.GET.get("ruolo", "")
        ctx["q"] = self.request.GET.get("q", "")
        ctx["ruoli_nominabili"] = services.ruoli_nominabili(self.request.user, solo_capi=True)
        return ctx


class UtenteDetailView(StaffPlanciaRequiredMixin, DetailView):
    """Dettaglio utente con storico nomine."""

    model = User
    template_name = "accounts/utente_detail.html"
    context_object_name = "utente"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.object
        ctx["nomine"] = u.nomine.select_related("nominato_da", "edizione").order_by("-creato_at")
        ctx["login_events"] = u.login_events.all()[:20]
        attore = self.request.user
        ctx["ruoli_nominabili"] = services.ruoli_nominabili(attore)
        ctx["puo_impersonare"] = (
            attore.ruolo in {"admin", "segreteria"} or attore.is_superuser
        )
        from apps.editions.models import Edizione
        ctx["edizioni"] = Edizione.objects.order_by("-anno")
        return ctx


class NominaView(StaffPlanciaRequiredMixin, View):
    """Assegna un ruolo a un utente (POST)."""

    def post(self, request, pk):
        utente = get_object_or_404(User, pk=pk)
        ruolo_target = request.POST.get("ruolo")
        if not ruolo_target or ruolo_target not in Ruolo.values:
            messages.error(request, "Ruolo non valido.")
            return redirect("accounts:utente_detail", pk=pk)

        edizione = None
        edizione_pk = request.POST.get("edizione")
        if edizione_pk:
            from apps.editions.models import Edizione
            edizione = get_object_or_404(Edizione, pk=edizione_pk)

        scadenza = request.POST.get("scadenza") or None

        try:
            service_nomina(request.user, utente, ruolo_target, edizione=edizione, scadenza=scadenza)
            messages.success(
                request,
                f"Ruolo {Ruolo(ruolo_target).label} assegnato a {utente.nome_completo}.",
            )
        except (PermissionError, ValueError) as e:
            messages.error(request, str(e))

        return redirect("accounts:utente_detail", pk=pk)


class CreaUtenteDaSocioView(StaffPlanciaRequiredMixin, View):
    """Crea un account utente per un Socio(capo) importato e lo nomina al ruolo scelto.

    Accessibile ad Admin, Segreteria e Incaricato EG dalla pagina utenti.
    """

    def post(self, request):
        socio_pk = request.POST.get("socio_pk")
        ruolo_target = request.POST.get("ruolo")

        if not socio_pk or not ruolo_target or ruolo_target not in Ruolo.values:
            messages.error(request, "Dati non validi.")
            return redirect("accounts:utente_list")
        try:
            utente, _ = services.crea_utente_da_socio(request.user, socio_pk, ruolo_target)
        except PermissionDenied as e:
            messages.error(request, str(e))
            return redirect("accounts:utente_list")
        except ValidationError as e:
            messages.error(request, _primo_messaggio(e))
            return redirect("accounts:utente_list")
        except (PermissionError, ValueError) as e:
            messages.error(request, str(e))
            # l'account può essere stato creato anche se la nomina è fallita
            utente = User.objects.filter(socio__pk=socio_pk).first()
            if utente is None:
                return redirect("accounts:utente_list")
            return redirect("accounts:utente_detail", pk=utente.pk)
        messages.success(
            request,
            f"Account creato e ruolo {Ruolo(ruolo_target).label} assegnato a {utente.socio}.",
        )
        return redirect("accounts:utente_detail", pk=utente.pk)


class CreaUtenteStaffView(StaffPlanciaRequiredMixin, View):
    """Crea un utente Admin/Segreteria/IABR senza Socio AGESCI e invia link per impostare la password."""

    template_name = "accounts/crea_utente_staff.html"

    def _ruoli_creabili(self, attore) -> list[tuple[str, str]]:
        return services.ruoli_staff_creabili(attore)

    def get(self, request):
        return render(request, self.template_name, {
            "ruoli_creabili": self._ruoli_creabili(request.user),
        })

    def post(self, request):
        email = request.POST.get("email", "").strip().lower()
        ruolo = request.POST.get("ruolo", "")
        try:
            utente, _, creato = services.crea_utente_staff(
                request.user,
                email,
                request.POST.get("first_name", ""),
                request.POST.get("last_name", ""),
                ruolo,
                request=request,
            )
        except ValidationError as exc:
            messages.error(request, _primo_messaggio(exc))
            return render(request, self.template_name, {
                "ruoli_creabili": self._ruoli_creabili(request.user)
            })
        except (PermissionError, ValueError) as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, {
                "ruoli_creabili": self._ruoli_creabili(request.user)
            })

        azione = "creato" if creato else "già esistente — nomina aggiunta"
        messages.success(
            request,
            f"Utente {email} {azione} con ruolo {Ruolo(ruolo).label}. "
            "È stata inviata un'email per impostare la password.",
        )
        return redirect("accounts:utente_detail", pk=utente.pk)


class CambiaRuoloView(LoginRequiredMixin, View):
    """Cambia il ruolo attivo dell'utente corrente (POST).

    Valida che il ruolo richiesto sia presente tra i ruoli attivi non scaduti
    dell'utente prima di aggiornare User.ruolo.
    """

    def post(self, request):
        ruolo_target = request.POST.get("ruolo", "")
        next_url = request.POST.get("next") or "/"

        try:
            cambiato = services.cambia_ruolo_attivo(request.user, ruolo_target)
        except ValidationError as exc:
            messages.error(request, _primo_messaggio(exc))
            return redirect(next_url)
        if not cambiato:
            return redirect(next_url)
        messages.success(
            request,
            f"Stai operando come {Ruolo(ruolo_target).label}.",
        )
        return redirect(next_url)


class TerminaSessioniView(LoginRequiredMixin, View):
    """Termina tutte le sessioni attive dell'utente tranne quella corrente.

    Usa UserSession.end() che cancella sia il record allauth che la django_session
    sottostante — il semplice .delete() rimuoverebbe solo il tracciamento allauth
    lasciando l'utente autenticato nel browser remoto.
    """

    def post(self, request):
        count = services.termina_altre_sessioni(request.user, request.session.session_key)
        if count:
            messages.success(request, f"Terminate {count} sessione/i attiva/e.")
        else:
            messages.info(request, "Nessun'altra sessione attiva da terminare.")
        return redirect("accounts:profilo")


class PlanciaPasswordChangeView(AllauthPasswordChangeView):
    """Cambio password con redirect al profilo + prompt termina sessioni."""

    def form_valid(self, form):
        from django.urls import reverse
        super().form_valid(form)
        return redirect(reverse("accounts:profilo") + "?dopo_cambio_password=1")
