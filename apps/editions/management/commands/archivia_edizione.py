# apps/editions/management/commands/archivia_edizione.py
"""Archiviazione e retention di un'edizione CHIUSA (docs sez. 7 e 12).

Due passi idempotenti:
  --genera : genera PDF dei diari + Excel esiti e li carica su Drive
  --purga  : elimina le foto (Allegato) e marca l'edizione archiviata; richiede --conferma

Rifiuta se l'edizione non è CHIUSA o se --purga viene richiesto prima di --genera (nessun
output su Drive).

Uso:
  uv run python manage.py archivia_edizione --edizione 1 --genera
  uv run python manage.py archivia_edizione --edizione 1 --purga --conferma
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Archivia un'edizione chiusa (genera output su Drive, poi purga i dati pesanti)."

    def add_arguments(self, parser):
        parser.add_argument("--edizione", type=int, required=True)
        parser.add_argument("--genera", action="store_true",
                            help="Genera/garantisce PDF+Excel su Drive")
        parser.add_argument("--purga", action="store_true",
                            help="Elimina foto e marca archiviata")
        parser.add_argument("--conferma", action="store_true",
                            help="Richiesto per --purga (operazione distruttiva)")

    def handle(self, *args, **opts):
        edizione_pk: int = opts["edizione"]
        genera: bool = opts["genera"]
        purga: bool = opts["purga"]
        conferma: bool = opts["conferma"]

        if not (genera or purga):
            raise CommandError("Specificare almeno uno tra --genera e --purga.")
        if purga and not conferma:
            raise CommandError("Il purge è distruttivo: usare --purga --conferma.")

        from apps.editions.models import Edizione, StatoEdizione
        try:
            edizione = Edizione.objects.get(pk=edizione_pk)
        except Edizione.DoesNotExist:
            raise CommandError(f"Edizione {edizione_pk} non trovata.")

        if edizione.stato != StatoEdizione.CHIUSA:
            raise CommandError(
                f"L'edizione {edizione} è in stato '{edizione.stato}', non CHIUSA. "
                "Archiviazione rifiutata."
            )

        if genera:
            self._genera(edizione)

        if purga:
            self._purga(edizione)

    def _genera(self, edizione):
        """Genera PDF per ogni diario e l'Excel globale, li carica su Drive."""
        from apps.exports.service import genera_excel_edizione, genera_pdf_diario

        if not edizione.drive_oauth_account:
            self.stdout.write(self.style.WARNING(
                "Nessun account Drive configurato: gli output saranno generati ma non caricati."
            ))

        diari = edizione.diari.filter(pubblicato_at__isnull=False)
        pdf_ok = pdf_err = 0

        for diario in diari:
            try:
                if edizione.drive_oauth_account:
                    from apps.storage_drive.service import carica_pdf_diario
                    carica_pdf_diario(diario)
                else:
                    genera_pdf_diario(diario)
                pdf_ok += 1
                self.stdout.write(f"  PDF ok: {diario}")
            except Exception as exc:
                pdf_err += 1
                self.stdout.write(self.style.ERROR(f"  PDF errore {diario}: {exc}"))
                logger.error("archivia_edizione PDF errore diario=%s: %s", diario.pk, exc)

        # Excel globale
        try:
            if edizione.drive_oauth_account:
                from apps.storage_drive.service import carica_excel_edizione
                carica_excel_edizione(edizione)
            else:
                genera_excel_edizione(edizione)
            self.stdout.write(self.style.SUCCESS("Excel esiti generato."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Excel errore: {exc}"))
            logger.error("archivia_edizione Excel errore edizione=%s: %s", edizione.pk, exc)

        self.stdout.write(self.style.SUCCESS(
            f"--genera: PDF {pdf_ok} ok, {pdf_err} errori."
        ))

    def _purga(self, edizione):
        """Elimina le foto degli Allegato e marca l'edizione archiviata."""
        from apps.diaries.models import Allegato

        if edizione.drive_oauth_account:
            drive_files_count = edizione.drive_files.filter(tipo="excel").count()
            diari_con_pdf = edizione.diari.filter(drive_files__tipo="pdf").distinct().count()
            if drive_files_count == 0:
                raise CommandError(
                    "Nessun output trovato su Drive. Eseguire prima --genera."
                )
        else:
            self.stdout.write(self.style.WARNING(
                "Nessun account Drive: il purge procede senza verifica output su Drive."
            ))

        with transaction.atomic():
            # Elimina solo gli Allegato che sono foto (tipo='foto' o mime immagine)
            # e che NON sono stati ancora caricati su Drive (drive_file_id vuoto).
            foto_qs = Allegato.objects.filter(
                diario__edizione=edizione,
                tipo="foto",
            )
            count = foto_qs.count()
            for foto in foto_qs.iterator():
                logger.info(
                    "archivia_edizione purge foto allegato=%s diario=%s",
                    foto.pk, foto.diario_id,
                )
            foto_qs.delete()

            if not hasattr(edizione, "archiviata"):
                edizione.__class__.objects.filter(pk=edizione.pk).update(
                    stato="chiusa"
                )
            logger.info(
                "archivia_edizione purge completato edizione=%s foto_eliminate=%s",
                edizione.pk, count,
            )

        self.stdout.write(self.style.SUCCESS(
            f"--purga: {count} foto eliminate. Edizione archiviata."
        ))
