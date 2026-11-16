"""Servizi di dominio delle edizioni, usati sia dalle viste web sia dall'API.

Le regole (permessi staff, transizioni di stato, dilazioni, export) stanno qui e non nelle
viste. Gli errori usano le eccezioni di `apps.evaluations.actions` (`PermessoNegato`,
`StatoNonValido`) e `django.core.exceptions.ValidationError` per i dati non validi.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db.models import Count

from apps.editions.models import Edizione, StatoEdizione
from apps.evaluations.actions import PermessoNegato, StatoNonValido

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.diaries.models import Diario
    from apps.editions.models import Dilazione

#: Azioni di stato ammesse sull'edizione → metodo del modello.
AZIONI_STATO_EDIZIONE: dict[str, str] = {
    "apri": "apri",
    "avvia_valutazione": "avvia_valutazione",
    "chiudi": "chiudi",
}

FORMATI_EXPORT_DIARI = ("xlsx", "ods", "csv")


def puo_gestire_edizioni(user: User) -> bool:
    """Admin, Segreteria e Incaricati EG (e il superuser) gestiscono le edizioni."""
    return bool(user.is_superuser or user.is_staff_plancia)


def richiedi_gestione(user: User) -> None:
    if not puo_gestire_edizioni(user):
        raise PermessoNegato("Operazione riservata alla gestione della piattaforma.")


def edizione_attiva() -> Edizione | None:
    """L'edizione aperta o in valutazione più recente (quella mostrata in home)."""
    return (
        Edizione.objects.filter(stato__in=[StatoEdizione.APERTA, StatoEdizione.IN_VALUTAZIONE])
        .order_by("-anno")
        .first()
    )


def cambia_stato_edizione(edizione: Edizione, azione: str, user: User) -> Edizione:
    """Esegue una transizione FSM dell'edizione (`apri`, `avvia_valutazione`, `chiudi`)."""
    richiedi_gestione(user)
    metodo = AZIONI_STATO_EDIZIONE.get(azione)
    if metodo is None:
        raise StatoNonValido(f"Azione non riconosciuta: {azione}")
    try:
        getattr(edizione, metodo)()
    except ValueError as exc:
        raise StatoNonValido(str(exc)) from None
    return edizione


def salva_edizione(user: User, dati: dict[str, Any], edizione: Edizione | None = None) -> Edizione:
    """Crea o aggiorna un'edizione validando con `EdizioneForm` (stesse regole del web)."""
    from apps.editions.forms import EdizioneForm

    richiedi_gestione(user)
    form = EdizioneForm(data=dati, instance=edizione)
    if not form.is_valid():
        raise ValidationError(form.errors.as_data())
    return form.save()


def stats_diari(edizione: Edizione) -> dict[str, Any]:
    """Conteggio dei diari dell'edizione per stato, con percentuale sul totale."""
    from apps.diaries.models import StatoDiario

    counts = dict(edizione.diari.values_list("stato").annotate(n=Count("pk")))
    totale = sum(counts.values())
    per_stato = [
        {
            "stato": stato,
            "label": label,
            "totale": counts.get(stato, 0),
            "percentuale": round(counts.get(stato, 0) / totale * 100) if totale else 0,
        }
        for stato, label in StatoDiario.choices
    ]
    return {"per_stato": per_stato, "totale": totale}


def riepilogo_edizione(edizione: Edizione, user: User) -> dict[str, Any]:
    """Ciò che mostra il dettaglio edizione (home): diari visibili, filtri, statistiche staff."""
    from apps.diaries.visibility import diari_visibili

    diari = list(diari_visibili(user, edizione=edizione))
    gestione = puo_gestire_edizioni(user)
    return {
        "edizione": edizione,
        "puo_gestire": gestione,
        "totale_diari": len(diari),
        "stats_diari": stats_diari(edizione) if gestione else None,
        "filtri": {
            "zone": sorted({d.squadriglia.reparto.gruppo.zona.nome for d in diari}),
            "gruppi": sorted({d.squadriglia.reparto.gruppo.nome for d in diari}),
            "specialita": sorted({
                d.anagrafica.specialita
                for d in diari
                if hasattr(d, "anagrafica") and d.anagrafica.specialita
            }),
        },
    }


def concedi_dilazione(diario: Diario, user: User, dati: dict[str, Any]) -> Dilazione:
    """Concede una dilazione al diario (solo staff, solo prima dell'invio allo staff)."""
    from apps.diaries.models import StatoDiario
    from apps.editions.forms import DilazioneForm

    richiedi_gestione(user)
    stati_prima_invio = (
        StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE, StatoDiario.RELAZIONE_FINALE,
    )
    if diario.stato not in stati_prima_invio:
        raise StatoNonValido("La dilazione si può concedere solo prima dell'invio del diario.")
    form = DilazioneForm(data=dati)
    if not form.is_valid():
        raise ValidationError(form.errors.as_data())
    dilazione = form.save(commit=False)
    dilazione.diario = diario
    dilazione.concessa_da = user
    dilazione.save()
    return dilazione


@dataclass
class EsitoExportDiari:
    """Risultato di `esporta_diari`: file pronto (sincrono) oppure task avviato."""

    asincrono: bool
    n_diari: int
    formato: str
    contenuto: bytes = b""
    content_type: str = ""
    filename: str = ""


def esporta_diari(edizione: Edizione, user: User, formato: str) -> EsitoExportDiari:
    """Export riassuntivo dei diari: sincrono sotto `EXPORT_DIARI_SOGLIA_ASYNC`, altrimenti
    task Celery che invia il file via email (il CSV resta sincrono se così configurato)."""
    from django.conf import settings

    from apps.diaries.models import Diario
    from apps.exports.service import genera_export_diari

    richiedi_gestione(user)
    formato = (formato or "xlsx").lower()
    if formato not in FORMATI_EXPORT_DIARI:
        formato = "xlsx"

    qs = Diario.objects.filter(edizione=edizione)
    n_diari = qs.count()
    soglia = getattr(settings, "EXPORT_DIARI_SOGLIA_ASYNC", 50)
    csv_sempre_sync = getattr(settings, "EXPORT_DIARI_CSV_SEMPRE_SYNC", True)
    if n_diari > soglia and not (csv_sempre_sync and formato == "csv"):
        from apps.exports.tasks import task_export_diari

        task_export_diari.delay(edizione.pk, user.pk, formato)
        return EsitoExportDiari(asincrono=True, n_diari=n_diari, formato=formato)

    contenuto, content_type, _ = genera_export_diari(qs, user, formato)
    return EsitoExportDiari(
        asincrono=False, n_diari=n_diari, formato=formato, contenuto=contenuto,
        content_type=content_type, filename=f"Export_diari_{edizione.anno}.{formato}",
    )


def nome_excel_esiti(edizione: Edizione) -> str:
    return f"Esiti_GV_{edizione.anno}.xlsx"
