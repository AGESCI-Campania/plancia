# apps/exports/service.py
"""Generazione PDF (WeasyPrint) ed Excel (openpyxl). Vedi docs sez. 11."""
from __future__ import annotations

import io
from pathlib import Path

from django.conf import settings

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


def _compress_image_for_pdf(raw: bytes, mime: str, max_px: int = 480) -> tuple[bytes, str]:
    """Ridimensiona e comprime l'immagine per l'embedding nel PDF.

    Le immagini nel template sono 120×90pt (~250×188px a 150dpi).
    480px sul lato maggiore è il doppio della risoluzione di stampa — ottima qualità,
    dimensione file ridotta dell'80-90% rispetto agli originali.
    """
    import io

    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_px:
            ratio = max_px / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except (UnidentifiedImageError, Exception):
        return raw, mime  # formato non supportato: usa l'originale


def _fetch_foto_drive(allegati, max_count: int = 6, budget_sec: float = 60.0) -> list[dict]:
    """Scarica le immagini da Drive, le comprime per il PDF e restituisce {nome, src} base64.

    Limita il numero di immagini (max_count) e il tempo totale (budget_sec).
    """
    import base64
    import io
    import time

    foto = []
    deadline = time.monotonic() + budget_sec

    for a in allegati[:max_count]:
        if time.monotonic() >= deadline:
            break
        if not a.drive_file_id or not a.mime.startswith("image/"):
            continue
        try:
            from googleapiclient.http import MediaIoBaseDownload

            from apps.storage_drive.service import _build_drive_service, _get_credenziali

            cred = _get_credenziali(a.diario.edizione)
            service = _build_drive_service(cred)
            req = service.files().get_media(fileId=a.drive_file_id)
            buf = io.BytesIO()
            dl = MediaIoBaseDownload(buf, req, chunksize=2 * 1024 * 1024)
            done = False
            while not done:
                if time.monotonic() >= deadline:
                    break
                _, done = dl.next_chunk()
            else:
                raw = buf.getvalue()
                compressed, out_mime = _compress_image_for_pdf(raw, a.mime)
                b64 = base64.b64encode(compressed).decode()
                foto.append({"nome": a.nome, "src": f"data:{out_mime};base64,{b64}"})
        except Exception:
            pass  # immagine non disponibile: la saltiamo nel PDF
    return foto


def genera_pdf_diario(diario, include_relazione: bool = False) -> bytes:
    """Genera il PDF del diario.

    include_relazione: se True include la Relazione finale CRP (modulo 6).
    Non passare True per i Capi Squadriglia — docs §15.
    """
    import weasyprint

    from apps.diaries.models import Allegato
    from apps.siteconfig.models import Impostazioni

    imp = Impostazioni.get()

    imprese = list(diario.imprese.prefetch_related("posti_azione", "esiti_specialita"))
    all_foto = list(Allegato.objects.filter(
        diario=diario, mime__startswith="image/"
    ).only("pk", "diario_id", "modulo", "drive_file_id", "mime", "nome"))

    for imp_obj in imprese:
        modulo_key = f"impresa_{imp_obj.numero}"
        imp_obj.pdf_foto = _fetch_foto_drive(
            [a for a in all_foto if a.modulo == modulo_key]
        )

    missione = getattr(diario, "missione", None)
    missione_foto = _fetch_foto_drive(
        [a for a in all_foto if a.modulo == "missione"]
    ) if missione else []

    relazione_finale = None
    if include_relazione:
        relazione_finale = getattr(diario, "relazione_finale", None)

    context = {
        "diario": diario,
        "anagrafica": getattr(diario, "anagrafica", None),
        "presentazione": getattr(diario, "presentazione", None),
        "imprese": imprese,
        "missione": missione,
        "missione_foto": missione_foto,
        "relazione_finale": relazione_finale,
        "titolo_piattaforma": imp.titolo,
        "sottotitolo_piattaforma": imp.sottotitolo,
    }

    template_html = _get_pdf_template_html()

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
