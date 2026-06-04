# apps/imports/management/commands/import_coca.py
"""Import capi dal tracciato Co.Ca. (Appendice D.2).

CSV: prima riga 'sep=,', valori come ="..." da ripulire, separatore ','.
Upsert idempotente su Socio(categoria=capo) per codice_socio.
L'email del capo NON è modificabile dal capo stesso.

Uso: uv run python manage.py import_coca path/al/file.csv [--dry-run]
"""
from __future__ import annotations

import csv
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch, TipoImport
from apps.org.models import Categoria, Gruppo, Socio, Zona

logger = logging.getLogger(__name__)


def leggi_csv(path: str, delimiter: str = ",") -> list[dict]:
    """Legge un CSV gestendo le righe iniziali non-dati.

    Salta (in qualunque ordine e combinazione):
    - righe ``sep=X`` (direttiva Excel per il separatore)
    - righe con ID evento (es. ``Evento24139``)
    Se la riga ``sep=`` è presente, il delimitatore viene auto-rilevato
    ignorando il parametro ``delimiter``.
    Le colonne senza intestazione (chiave vuota o None) vengono scartate.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = f.read()

    lines = raw.splitlines(keepends=True)
    detected_delimiter = delimiter
    skip = 0
    for line in lines:
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("sep="):
            sep_char = stripped[4:].strip()
            if sep_char:
                detected_delimiter = sep_char
            skip += 1
        elif stripped.startswith("Evento") or stripped.startswith("evento"):
            skip += 1
        else:
            break

    import io
    reader = csv.reader(io.StringIO(raw), delimiter=detected_delimiter)
    all_rows = list(reader)[skip:]

    if not all_rows:
        return []

    header_row = all_rows[0]
    return [
        {k: v for k, v in zip(header_row, row) if k is not None and k.strip() != ""}
        for row in all_rows[1:]
        if any(v.strip() for v in row if v)
    ]


def _clean(v: str) -> str:
    v = (v or "").strip()
    if v.startswith('="') and v.endswith('"'):
        v = v[2:-1]
    return v.strip()


def _get_or_create_zona_gruppo(zona_nome: str, gruppo_nome: str):
    zona, _ = Zona.objects.get_or_create(nome=zona_nome)
    gruppo, _ = Gruppo.objects.get_or_create(nome=gruppo_nome, zona=zona)
    return zona, gruppo


class Command(BaseCommand):
    help = "Importa i capi dal tracciato Co.Ca. (upsert per codice_socio)."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Percorso del file CSV")
        parser.add_argument("--dry-run", action="store_true", help="Non scrivere sul DB")

    def handle(self, *args, **opts):
        path: str = opts["path"]
        dry_run: bool = opts["dry_run"]

        try:
            rows = leggi_csv(path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        log = LogImportazione(tipo=TipoImport.COCA, file_nome=path)
        ok = scartati = 0
        riga_objs: list[RigaImportazione] = []

        # Salva il log PRIMA della transazione: sopravvive a un eventuale rollback
        # e compare sempre nello storico anche in caso di errore.
        if not dry_run:
            log.save()

        try:
            with transaction.atomic():
                for i, row in enumerate(rows, 1):
                    codice = _clean(row.get("CODICE SOCIO", ""))
                    if not codice or not codice.isdigit() or not (4 <= len(codice) <= 8):
                        scartati += 1
                        if not dry_run:
                            riga_objs.append(RigaImportazione(
                                log=log, numero=i, dati_grezzi=row,
                                stato_match=StatoMatch.SCARTATA,
                                note="Codice socio non valido",
                            ))
                        continue

                    zona_nome = _clean(row.get("ZONA", "")) or "Sconosciuta"
                    gruppo_nome = _clean(row.get("GRUPPO", "")) or "Sconosciuto"

                    if not dry_run:
                        sp = transaction.savepoint()
                        try:
                            zona, gruppo = _get_or_create_zona_gruppo(zona_nome, gruppo_nome)
                            Socio.objects.update_or_create(
                                codice_socio=codice,
                                defaults={
                                    "nome": _clean(row.get("NOME", "")),
                                    "cognome": _clean(row.get("COGNOME", "")),
                                    "email": _clean(row.get("EMAIL", "")),
                                    "cellulare": _clean(row.get("CELLULARE", ""))[:50],
                                    "branca": _clean(row.get("BRANCA", ""))[:60],
                                    "status": _clean(row.get("STATUS SOCIO", ""))[:100],
                                    "categoria": Categoria.CAPO,
                                    "zona": zona,
                                    "gruppo": gruppo,
                                },
                            )
                            transaction.savepoint_commit(sp)
                            riga_objs.append(RigaImportazione(
                                log=log, numero=i, dati_grezzi=row,
                                stato_match=StatoMatch.OK,
                            ))
                            ok += 1
                        except Exception as exc:
                            transaction.savepoint_rollback(sp)
                            scartati += 1
                            logger.warning("Co.Ca. riga %d (codice %s): %s", i, codice, exc)
                            riga_objs.append(RigaImportazione(
                                log=log, numero=i, dati_grezzi=row,
                                stato_match=StatoMatch.SCARTATA,
                                note=str(exc)[:255],
                            ))
                    else:
                        ok += 1

                if not dry_run:
                    RigaImportazione.objects.bulk_create(riga_objs)
                    log.totale = ok + scartati
                    log.ok = ok
                    log.scartati = scartati
                    log.save(update_fields=["totale", "ok", "scartati"])

                if dry_run:
                    transaction.set_rollback(True)

        except Exception as exc:
            if not dry_run:
                log.scartati = scartati
                log.totale = ok + scartati
                log.save(update_fields=["totale", "ok", "scartati"])
            raise CommandError(f"Errore durante l'import: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY-RUN] ' if dry_run else ''}Co.Ca.: {ok} ok, {scartati} scartati."
        ))

