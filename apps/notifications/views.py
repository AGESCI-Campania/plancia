# apps/notifications/views.py
"""Viste per attivazione inviti, gestione e invio notifiche. Vedi docs sez. 8."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.mixins import RuoloRequiredMixin
from apps.accounts.models import Ruolo
from apps.notifications.models import Invito, StatoInvito, TipoInvito

_STAFF = (Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG)


class AttivazoneInvitoView(View):
    """Attiva il token di un invito.

    Per gli inviti standard (Capi Reparto, PGV): autentica direttamente su GET.
    Per gli inviti Capo Squadriglia (tipo CODICE_SOCIO): mostra un form che richiede
    la conferma del codice socio e l'inserimento/conferma dell'email, poi autentica.
    """

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
            return render(
                request,
                "notifications/conferma_codice_socio.html",
                {
                    "invito": invito,
                    "token": token,
                },
            )

        return self._attiva_e_login(request, invito)

    def post(self, request, token):
        invito = get_object_or_404(Invito, token=token)

        if invito.stato != StatoInvito.INVIATO:
            messages.error(request, "Questo invito non è più valido.")
            return redirect("account_login")

        codice = request.POST.get("codice_socio", "").strip()
        email = request.POST.get("email", "").strip().lower()

        socio = invito.utente.socio
        if not socio or codice != socio.codice_socio:
            messages.error(
                request,
                "Codice socio non corretto. Controlla il codice sulla tua tessera AGESCI.",
            )
            return render(
                request,
                "notifications/conferma_codice_socio.html",
                {
                    "invito": invito,
                    "token": token,
                    "email_inserita": email,
                },
            )

        # Valida email
        if not email:
            messages.error(request, "Inserisci il tuo indirizzo email.")
            return render(
                request,
                "notifications/conferma_codice_socio.html",
                {
                    "invito": invito,
                    "token": token,
                    "codice_inserito": codice,
                },
            )
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "L'indirizzo email non è valido.")
            return render(
                request,
                "notifications/conferma_codice_socio.html",
                {
                    "invito": invito,
                    "token": token,
                    "codice_inserito": codice,
                },
            )

        # Aggiorna email utente e socio se placeholder o diversa
        utente = invito.utente
        if utente.email.endswith("@noemail.internal") or utente.email != email:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            if User.objects.filter(email=email).exclude(pk=utente.pk).exists():
                messages.error(
                    request,
                    "Questa email è già registrata. Se hai già un account contatta la segreteria.",
                )
                return render(
                    request,
                    "notifications/conferma_codice_socio.html",
                    {
                        "invito": invito,
                        "token": token,
                        "codice_inserito": codice,
                        "email_inserita": email,
                    },
                )
            utente.email = email
            utente.save(update_fields=["email"])
            if socio and socio.email != email:
                socio.email = email
                socio.save(update_fields=["email"])

        return self._attiva_e_login(request, invito)

    def _attiva_e_login(self, request, invito: Invito):
        invito.attiva()
        utente = invito.utente
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

        # CRP può reinviare solo gli inviti CSQ dei propri diari
        if request.user.ruolo == Ruolo.CRP and (
            not invito.diario
            or invito.ruolo_target != Ruolo.CSQ
            or invito.diario.crp != request.user.socio
        ):
            messages.error(request, "Non sei autorizzato a reinviare questo invito.")
            return redirect(request.POST.get("next") or "diaries:list")

        from apps.notifications.service import reinvia_invito

        reinvia_invito(invito)
        messages.success(request, f"Invito reinviato a {invito.utente.email}.")
        return redirect(request.POST.get("next") or "notifications:gestione_inviti")


class InvitiCrpView(RuoloRequiredMixin, View):
    """Pagina del Capo Reparto per monitorare e reinviare gli inviti ai propri Capi Squadriglia."""

    ruoli_ammessi = (Ruolo.CRP,)
    template_name = "notifications/inviti_crp.html"

    def get(self, request):
        from apps.diaries.models import Diario
        from apps.editions.models import Edizione, StatoEdizione

        edizione = (
            Edizione.objects.filter(stato__in=[StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE])
            .order_by("-anno")
            .first()
        )
        ctx = {"edizione": edizione}

        if edizione and request.user.socio:
            diari = list(
                Diario.objects.filter(edizione=edizione, crp=request.user.socio)
                .select_related("csq__utente", "squadriglia__reparto")
                .prefetch_related("inviti")
                .order_by("squadriglia__nome")
            )
            for d in diari:
                inviti = sorted(d.inviti.all(), key=lambda x: x.inviato_at, reverse=True)
                d.ultimo_invito_csq = next(
                    (inv for inv in inviti if inv.ruolo_target == Ruolo.CSQ), None
                )
            ctx["diari"] = diari

        return render(request, self.template_name, ctx)


class InvioInvitiBulkView(RuoloRequiredMixin, View):
    """Invia tutti gli inviti mancanti per un diario (POST da dettaglio diario)."""

    ruoli_ammessi = _STAFF

    def post(self, request, diario_pk):
        from apps.diaries.models import Diario
        from apps.notifications.tasks import task_invia_inviti_bulk

        diario = get_object_or_404(Diario, pk=diario_pk)
        ruoli = request.POST.getlist("ruoli") or ["csq", "crp"]
        task_invia_inviti_bulk.delay(diario.pk, ruoli)
        messages.success(request, "Inviti accodati per l'invio.")
        return redirect("diaries:detail", pk=diario.pk)


class GestioneInvitiView(RuoloRequiredMixin, View):
    """Pagina per inviare e monitorare gli inviti dell'edizione attiva."""

    ruoli_ammessi = _STAFF
    template_name = "notifications/gestione_inviti.html"

    def get(self, request):
        from apps.diaries.models import Diario
        from apps.editions.models import Edizione, StatoEdizione

        edizione = (
            Edizione.objects.filter(stato__in=[StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE])
            .order_by("-anno")
            .first()
        )

        ctx = {"edizione": edizione}

        if edizione:
            diari = list(
                Diario.objects.filter(edizione=edizione)
                .select_related(
                    "csq__utente",
                    "crp__utente",
                    "squadriglia__reparto__gruppo__zona",
                )
                .prefetch_related("inviti")
                .order_by("squadriglia__reparto__nome", "squadriglia__nome")
            )
            # Precalcola l'ultimo invito per ruolo su ogni diario (usa la prefetch).
            for d in diari:
                inviti = sorted(
                    d.inviti.all(),
                    key=lambda x: x.inviato_at,
                    reverse=True,
                )
                d.ultimo_invito_csq = next(
                    (inv for inv in inviti if inv.ruolo_target == Ruolo.CSQ), None
                )
                d.ultimo_invito_crp = next(
                    (inv for inv in inviti if inv.ruolo_target == Ruolo.CRP), None
                )
            ctx["diari"] = diari
            ctx["stato_inviti"] = _calcola_stato_inviti(diari)
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
        from apps.editions.models import Edizione, StatoEdizione
        from apps.notifications.tasks import (
            task_invia_inviti_capi_edizione,
            task_invia_inviti_csq_edizione,
        )

        edizione = (
            Edizione.objects.filter(stato__in=[StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE])
            .order_by("-anno")
            .first()
        )
        if not edizione:
            messages.error(request, "Nessuna edizione attiva trovata.")
            return redirect("notifications:gestione_inviti")

        tipo = request.POST.get("tipo")
        backend_tipo = request.POST.get("backend_tipo", "massivo")
        if backend_tipo not in ("massivo", "standard", "smtp", "transazionale"):
            backend_tipo = "massivo"

        if tipo == "capi":
            task_invia_inviti_capi_edizione.delay(edizione.pk, backend_tipo=backend_tipo)
            messages.success(
                request,
                "Invio inviti ai Capi Reparto accodato. Riceveranno l'email entro pochi minuti.",
            )
        elif tipo == "csq":
            task_invia_inviti_csq_edizione.delay(edizione.pk, backend_tipo=backend_tipo)
            messages.success(
                request,
                "Invio inviti ai Capi Squadriglia accodato. "
                "I Capi Reparto riceveranno la lista dei loro Capi Squadriglia "
                "con i rispettivi link di accesso.",
            )
        else:
            messages.error(request, "Tipo di invito non riconosciuto.")

        return redirect("notifications:gestione_inviti")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _calcola_stato_inviti(diari) -> dict:
    """Restituisce contatori aggregati per la pagina gestione inviti."""
    from apps.notifications.models import StatoInvito

    capi_totale = capi_inviati = capi_attivati = 0
    csq_totale = csq_inviati = csq_attivati = 0

    for diario in diari:
        inviti_diario = list(diario.inviti.all())

        csq_totale += 1
        inv_csq = [i for i in inviti_diario if i.ruolo_target == "csq"]
        if any(i.stato == StatoInvito.ATTIVATO for i in inv_csq):
            csq_attivati += 1
        elif any(i.stato == StatoInvito.INVIATO for i in inv_csq):
            csq_inviati += 1

        if diario.crp:
            capi_totale += 1
            inv_crp = [i for i in inviti_diario if i.ruolo_target == "crp"]
            if any(i.stato == StatoInvito.ATTIVATO for i in inv_crp):
                capi_attivati += 1
            elif any(i.stato == StatoInvito.INVIATO for i in inv_crp):
                capi_inviati += 1

    return {
        "capi_totale": capi_totale,
        "capi_inviati": capi_inviati,
        "capi_attivati": capi_attivati,
        "capi_da_invitare": capi_totale - capi_inviati - capi_attivati,
        "csq_totale": csq_totale,
        "csq_inviati": csq_inviati,
        "csq_attivati": csq_attivati,
        "csq_da_invitare": csq_totale - csq_inviati - csq_attivati,
    }
