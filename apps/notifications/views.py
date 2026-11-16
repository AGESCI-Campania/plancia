# apps/notifications/views.py
"""Viste per attivazione inviti, gestione e invio notifiche. Vedi docs sez. 8.

La logica (permessi, verifiche, invio) sta in `apps.notifications.service`, condivisa
con l'API (`apps/api/routers/notifiche.py`).
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.notifications import service
from apps.notifications.models import Invito, StatoInvito, TipoInvito

_STAFF = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)


class AttivazoneInvitoView(View):
    """Attiva il token di un invito.

    Per gli inviti standard (Capi Reparto, PGV): autentica direttamente su GET.
    Per gli inviti Capo Squadriglia (tipo CODICE_SOCIO): mostra un form che richiede
    la conferma del codice socio e l'inserimento/conferma dell'email, poi autentica.
    """

    template_name = "notifications/conferma_codice_socio.html"

    def get(self, request, token):
        invito = get_object_or_404(Invito, token=token)

        if invito.stato == StatoInvito.ATTIVATO:
            messages.info(request, "Questo invito è già stato attivato.")
            return redirect("diaries:list")
        if invito.stato == StatoInvito.SCADUTO:
            messages.error(
                request,
                "Questo invito è scaduto. Contatta la segreteria per un nuovo invito.",
            )
            return redirect("account_login")

        if invito.tipo == TipoInvito.CODICE_SOCIO:
            return render(request, self.template_name, {"invito": invito, "token": token})

        return self._attiva_e_login(request, invito)

    def post(self, request, token):
        invito = get_object_or_404(Invito, token=token)

        if invito.stato != StatoInvito.INVIATO:
            messages.error(request, "Questo invito non è più valido.")
            return redirect("account_login")

        codice = request.POST.get("codice_socio", "").strip()
        email = request.POST.get("email", "").strip().lower()
        try:
            service.conferma_codice_socio(invito, codice, email)
        except ValidationError as exc:
            campi = exc.message_dict
            for msgs in campi.values():
                for m in msgs:
                    messages.error(request, m)
            ctx = {"invito": invito, "token": token, "email_inserita": email}
            if "codice_socio" not in campi:
                ctx["codice_inserito"] = codice
            return render(request, self.template_name, ctx)

        return self._attiva_e_login(request, invito)

    def _attiva_e_login(self, request, invito: Invito):
        utente = service.completa_attivazione_invito(invito)
        if not service.login_da_invito_consentito(utente):
            messages.success(request, "Invito attivato: accedi con le tue credenziali.")
            return redirect("account_login")
        utente.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, utente)
        messages.success(request, f"Benvenuto/a, {utente.get_full_name() or utente.email}!")

        if invito.diario:
            return redirect("diaries:detail", pk=invito.diario.pk)
        return redirect("diaries:list")


class ReinvioInvitoView(RuoloRequiredMixin, View):
    """Reinvia un invito (crea un nuovo token, invalida il vecchio).

    Accessibile a staff oppure al Capo Reparto per gli inviti al proprio Capo Squadriglia.
    """

    ruoli_ammessi = _STAFF + (Ruolo.CRP,)

    def post(self, request, pk):
        invito = get_object_or_404(Invito, pk=pk)
        try:
            service.verifica_reinvio(request.user, invito)
        except (PermissionDenied, ValidationError) as exc:
            messaggio = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            messages.error(request, messaggio)
            return redirect(request.POST.get("next") or "diaries:list")

        service.reinvia_invito(invito)
        messages.success(request, f"Invito reinviato a {invito.utente.email}.")
        return redirect(request.POST.get("next") or "notifications:gestione_inviti")


class InvitiCrpView(RuoloRequiredMixin, View):
    """Pagina del Capo Reparto per monitorare e reinviare gli inviti ai propri Capi Squadriglia."""

    ruoli_ammessi = (Ruolo.CRP,)
    template_name = "notifications/inviti_crp.html"

    def get(self, request):
        edizione = service.edizione_inviti_attiva()
        ctx = {"edizione": edizione}
        if edizione and request.user.socio:
            ctx["diari"] = service.diari_inviti_crp(edizione, request.user.socio)
        return render(request, self.template_name, ctx)


class InvioInvitiBulkView(RuoloRequiredMixin, View):
    """Invia tutti gli inviti mancanti per un diario (POST da dettaglio diario)."""

    ruoli_ammessi = _STAFF

    def post(self, request, diario_pk):
        from apps.diaries.models import Diario

        diario = get_object_or_404(Diario, pk=diario_pk)
        try:
            service.accoda_inviti_diario(diario, request.POST.getlist("ruoli"))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, "Inviti accodati per l'invio.")
        return redirect("diaries:detail", pk=diario.pk)


class GestioneInvitiView(RuoloRequiredMixin, View):
    """Pagina per inviare e monitorare gli inviti dell'edizione attiva."""

    ruoli_ammessi = _STAFF
    template_name = "notifications/gestione_inviti.html"

    def get(self, request):
        edizione = service.edizione_inviti_attiva()
        ctx = {"edizione": edizione}

        if edizione:
            diari = service.diari_con_ultimi_inviti(edizione)
            ctx["diari"] = diari
            ctx["stato_inviti"] = service.calcola_stato_inviti(diari)
            ctx["zone"] = sorted({d.squadriglia.reparto.gruppo.zona.nome for d in diari})
            ctx["gruppi"] = sorted({d.squadriglia.reparto.gruppo.nome for d in diari})

        from apps.siteconfig.models import BackendPosta, Impostazioni
        imp = Impostazioni.get()
        ctx["backend_massivo_label"] = BackendPosta(imp.email_backend_massivo).label

        return render(request, self.template_name, ctx)


class InviaInvitiEdizoneView(RuoloRequiredMixin, View):
    """Avvia l'invio bulk degli inviti per l'edizione attiva."""

    ruoli_ammessi = _STAFF

    def post(self, request):
        backend_tipo = request.POST.get("backend_tipo", "massivo")
        if backend_tipo not in ("massivo", "standard", "smtp", "transazionale"):
            backend_tipo = "massivo"
        try:
            esito = service.avvia_invio_inviti_edizione(
                service.edizione_inviti_attiva(), request.POST.get("tipo"), backend_tipo
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, esito)
        return redirect("notifications:gestione_inviti")


# Compatibilità: il nome storico dell'helper resta importabile.
_calcola_stato_inviti = service.calcola_stato_inviti
