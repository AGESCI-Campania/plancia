"""`manage.py manutenzione attiva|disattiva|stato` — usato da `scripts/aggiorna.sh`.

- `attiva [--messaggio "..."]`: attiva la modalità manutenzione (pagina/JSON 503 per chi non è Admin);
- `disattiva`: la disattiva;
- `stato`: stampa `attiva` oppure `disattiva` (exit code 0 in entrambi i casi).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.siteconfig.manutenzione import imposta_manutenzione, manutenzione_attiva


class Command(BaseCommand):
    help = "Attiva, disattiva o mostra lo stato della modalità manutenzione."

    def add_arguments(self, parser) -> None:
        parser.add_argument("azione", choices=["attiva", "disattiva", "stato"])
        parser.add_argument(
            "--messaggio", default=None,
            help="Messaggio mostrato agli utenti (solo con 'attiva'; vuoto = predefinito).",
        )

    def handle(self, *args, azione: str, messaggio: str | None = None, **options) -> None:
        if azione == "stato":
            self.stdout.write("attiva" if manutenzione_attiva() else "disattiva")
            return
        imposta_manutenzione(azione == "attiva", messaggio if azione == "attiva" else None)
        self.stdout.write("attiva" if azione == "attiva" else "disattiva")
