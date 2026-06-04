# apps/accounts/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from apps.accounts.mixins import StaffPlanciaRequiredMixin
from apps.accounts.models import Ruolo, User
from apps.accounts.roles import ROLE_CREATABLE_BY, nomina as service_nomina


class ProfiloView(LoginRequiredMixin, TemplateView):
    """Profilo dell'utente corrente. Email editabile solo dai CSQ (ragazzi)."""

    template_name = "accounts/profilo.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        ctx["nomine"] = u.nomine.select_related("nominato_da", "edizione").order_by("-creato_at")
        ctx["login_events"] = u.login_events.all()[:10]
        ctx["puo_modificare_email"] = (
            u.ruolo == Ruolo.CSQ and u.socio and u.socio.email_modificabile_dall_interessato
        )
        return ctx

    def post(self, request):
        """Aggiornamento email per i CSQ."""
        if not (request.user.ruolo == Ruolo.CSQ and request.user.socio):
            raise PermissionDenied
        email = request.POST.get("email", "").strip()
        if not email:
            messages.error(request, "L'indirizzo email non può essere vuoto.")
            return redirect("accounts:profilo")
        if User.objects.exclude(pk=request.user.pk).filter(email=email).exists():
            messages.error(request, "Questo indirizzo email è già in uso.")
            return redirect("accounts:profilo")
        request.user.email = email
        if request.user.socio:
            request.user.socio.email = email
            request.user.socio.save(update_fields=["email"])
        request.user.save(update_fields=["email"])
        messages.success(request, "Email aggiornata.")
        return redirect("accounts:profilo")


class UtenteListView(StaffPlanciaRequiredMixin, ListView):
    """Lista utenti — Admin, Segreteria, Incaricato EG."""

    model = User
    template_name = "accounts/utente_list.html"
    context_object_name = "utenti"
    paginate_by = 50

    def get_queryset(self):
        qs = User.objects.select_related("socio", "socio__gruppo", "socio__zona").order_by(
            "ruolo", "email"
        )
        ruolo = self.request.GET.get("ruolo")
        if ruolo in Ruolo.values:
            qs = qs.filter(ruolo=ruolo)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(email__icontains=q) | qs.filter(
                socio__cognome__icontains=q
            ) | qs.filter(socio__nome__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ruoli"] = Ruolo.choices
        ctx["ruolo_sel"] = self.request.GET.get("ruolo", "")
        ctx["q"] = self.request.GET.get("q", "")
        attore = self.request.user
        from apps.accounts.roles import ROLE_REQUIRES_CATEGORY
        ctx["ruoli_nominabili"] = [
            (r, label)
            for r, label in Ruolo.choices
            if (attore.ruolo in ROLE_CREATABLE_BY.get(r, set()) or attore.is_superuser)
            and ROLE_REQUIRES_CATEGORY.get(r) != "ragazzo"
        ]
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
        ctx["ruoli_nominabili"] = [
            (r, label)
            for r, label in Ruolo.choices
            if attore.ruolo in ROLE_CREATABLE_BY.get(r, set()) or attore.is_superuser
        ]
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
        from apps.org.models import Categoria, Socio

        socio_pk = request.POST.get("socio_pk")
        ruolo_target = request.POST.get("ruolo")

        if not socio_pk or not ruolo_target or ruolo_target not in Ruolo.values:
            messages.error(request, "Dati non validi.")
            return redirect("accounts:utente_list")

        socio = get_object_or_404(Socio, pk=socio_pk, categoria=Categoria.CAPO)

        # Verifica che l'attore possa creare quel ruolo
        if ruolo_target not in {
            r for r, creators in ROLE_CREATABLE_BY.items()
            if request.user.ruolo in creators or request.user.is_superuser
        }:
            messages.error(request, f"Non sei autorizzato ad assegnare il ruolo {Ruolo(ruolo_target).label}.")
            return redirect("accounts:utente_list")

        from apps.notifications.service import crea_o_ottieni_utente_per_socio

        utente = crea_o_ottieni_utente_per_socio(socio, ruolo_target)

        try:
            service_nomina(request.user, utente, ruolo_target)
            messages.success(
                request,
                f"Account creato e ruolo {Ruolo(ruolo_target).label} assegnato a {socio}.",
            )
        except (PermissionError, ValueError) as e:
            messages.error(request, str(e))

        return redirect("accounts:utente_detail", pk=utente.pk)


class CambiaRuoloView(LoginRequiredMixin, View):
    """Cambia il ruolo attivo dell'utente corrente (POST).

    Valida che il ruolo richiesto sia presente tra i ruoli attivi non scaduti
    dell'utente prima di aggiornare User.ruolo.
    """

    def post(self, request):
        ruolo_target = request.POST.get("ruolo", "")
        next_url = request.POST.get("next") or "/"

        if ruolo_target not in request.user.ruoli_attivi:
            messages.error(request, "Non hai questo ruolo attivo.")
            return redirect(next_url)

        if ruolo_target == request.user.ruolo:
            return redirect(next_url)

        request.user.ruolo = ruolo_target
        request.user.save(update_fields=["ruolo"])
        messages.success(
            request,
            f"Stai operando come {Ruolo(ruolo_target).label}.",
        )
        return redirect(next_url)
