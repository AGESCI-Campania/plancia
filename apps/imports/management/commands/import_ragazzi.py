# apps/imports/management/commands/import_ragazzi.py
"""Import ragazzi dal tracciato Co.Ca. senza colonna EMAIL (Appendice D.3).

Upsert idempotente su Socio(categoria=ragazzo). I ragazzi nascono senza email
(sarà aggiunta dall'import Evento ed è modificabile dal ragazzo).
Da Socio(ragazzo) si selezionano esclusivamente i CSQ.

Uso: uv run python manage.py import_ragazzi path/al/file.csv [--dry-run]
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch, TipoImport
from apps.org.models import Categoria, Socio

from .import_coca import _clean, _get_or_create_zona_gruppo, leggi_csv

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Importa i ragazzi (upsert per codice_socio, senza email)."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Percorso del file CSV")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        path: str = opts["path"]
        dry_run: bool = opts["dry_run"]

        try:
            rows = leggi_csv(path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        log = LogImportazione(tipo=TipoImport.RAGAZZI, file_nome=path)
        ok = scartati = 0
        riga_objs: list[RigaImportazione] = []

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
                                    "cellulare": _clean(row.get("CELLULARE", ""))[:50],
                                    "branca": _clean(row.get("BRANCA", ""))[:60],
                                    "status": _clean(row.get("STATUS SOCIO", ""))[:100],
                                    "categoria": Categoria.RAGAZZO,
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
                            logger.warning("Ragazzi riga %d (codice %s): %s", i, codice, exc)
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
            f"{'[DRY-RUN] ' if dry_run else ''}Ragazzi: {ok} ok, {scartati} scartati."
        ))
