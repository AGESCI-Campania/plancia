# apps/exports/service.py
"""Generazione PDF (WeasyPrint) ed Excel (openpyxl). Vedi docs sez. 11."""
from __future__ import annotations

import io
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _get_pdf_template_html() -> str:
    """Restituisce il template HTML attivo (DB o file di default)."""
    from apps.exports.models import PdfTemplate

    try:
        tpl = PdfTemplate.objects.get(chiave="diario", attivo=True)
        return tpl.contenuto_html
    except PdfTemplate.DoesNotExist:
        path = Path(settings.BASE_DIR) / "templates" / "exports" / "diario.html"
        return path.read_text(encoding="utf-8")


def genera_pdf_diario(diario) -> bytes:
    """Genera il PDF del diario. Il template non include Relazione né Valutazione (docs §15)."""
    import weasyprint

    from apps.siteconfig.models import Impostazioni

    imp = Impostazioni.get()

    # Raccolta dati moduli (mai relazione/valutazione nel PDF del CSQ — docs sez. 15)
    context = {
        "diario": diario,
        "anagrafica": getattr(diario, "anagrafica", None),
        "presentazione": getattr(diario, "presentazione", None),
        "imprese": diario.imprese.prefetch_related("posti_azione", "esiti_specialita"),
        "missione": getattr(diario, "missione", None),
        # relazione e valutazione deliberatamente escluse
        "titolo_piattaforma": imp.titolo,
        "sottotitolo_piattaforma": imp.sottotitolo,
    }

    template_html = _get_pdf_template_html()

    # Sostituisce il template con render_to_string se è un path relativo
    from django.template import Context, Template
    rendered = Template(template_html).render(Context(context))

    return weasyprint.HTML(string=rendered, base_url=str(settings.BASE_DIR)).write_pdf()


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def genera_excel_edizione(edizione) -> bytes:
    """Genera un Excel con una riga per diario e fogli per zona. Vedi docs sez. 11."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws_riepilogo = wb.active
    ws_riepilogo.title = "Riepilogo"

    header = [
        "Zona", "Gruppo", "Reparto", "Squadriglia", "Tipo",
        "CSQ Cognome", "CSQ Nome", "CRP Cognome", "CRP Nome",
        "Stato", "Scadenza", "Specialità",
        "Esito", "Pubblicato", "Note valutazione",
    ]
    ws_riepilogo.append(header)
    # Stile intestazione
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="5AA02C")
    for i, _ in enumerate(header, 1):
        cell = ws_riepilogo.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill

    diari = (
        edizione.diari
        .select_related("squadriglia__reparto__gruppo__zona", "csq", "crp")
        .prefetch_related("anagrafica", "valutazione")
        .order_by(
            "squadriglia__reparto__gruppo__zona__nome",
            "squadriglia__reparto__gruppo__nome",
            "squadriglia__nome",
        )
    )

    zone_viste: dict[str, object] = {}

    for d in diari:
        sq = d.squadriglia
        zona_nome = sq.reparto.gruppo.zona.nome
        ana = getattr(d, "anagrafica", None)
        val = getattr(d, "valutazione", None)

        riga = [
            zona_nome,
            sq.reparto.gruppo.nome,
            sq.reparto.nome,
            sq.nome,
            d.get_tipo_display(),
            d.csq.cognome if d.csq else "",
            d.csq.nome if d.csq else "",
            d.crp.cognome if d.crp else "",
            d.crp.nome if d.crp else "",
            d.get_stato_display(),
            str(d.scadenza_effettiva() or ""),
            ana.specialita if ana else "",
            val.get_esito_display() if val and val.esito else "",
            "Sì" if d.pubblicato else "No",
            val.note if val else "",
        ]
        ws_riepilogo.append(riga)

        # Un foglio per zona
        if zona_nome not in zone_viste:
            ws_zona = wb.create_sheet(zona_nome[:31])
            ws_zona.append(header)
            zone_viste[zona_nome] = ws_zona
        zone_viste[zona_nome].append(riga)

    # Larghezze colonne automatiche
    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = max((len(str(c.value or "")) for c in col), default=10)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 2, 40)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
