# apps/imports/management/commands/import_squadriglie.py
"""Import squadriglie iscritte dal tracciato Evento (Appendice D.1).

L'import capi (Co.Ca.) deve essere eseguito PRIMA di questo, perché il CRP
viene cercato per email tra i Socio(capo) già presenti. Le righe senza match
CRP vengono salvate come 'da_riconciliare' e possono essere riproposte in
seguito senza re-importare il file, ad esempio dopo un nuovo import capi o
l'inserimento manuale del capo (pulsante "Riprova anomalie" nella UI).

CSV: UTF-8 con BOM, separatore ';'.
- CSQ: Codice + Cognome + Nome → upsert Socio(ragazzo); email aggiornata se presente.
- CRP: match Socio(capo) per email (EmailReferente); fallback per nome/cognome.
- Crea Diario + Anagrafica; tipo = rinnovo se "E' una riconferma?" == sì.

Uso: uv run python manage.py import_squadriglie path/al/file.csv --edizione <pk> [--dry-run]
"""
from __future__ import annotations

import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch, TipoImport
from apps.org.models import Categoria, Reparto, Socio, Squadriglia

from .import_coca import _clean, _get_or_create_zona_gruppo

SI = {"si", "sì", "s", "true", "x", "1"}


def _parse_crp_nome(raw: str) -> tuple[str, str]:
    """Converte 'COGNOME, NOME' in (cognome, nome)."""
    if "," in raw:
        parti = raw.split(",", 1)
        return parti[0].strip().title(), parti[1].strip().title()
    parti = raw.strip().split()
    if len(parti) >= 2:
        return " ".join(parti[:-1]).title(), parti[-1].title()
    return raw.strip().title(), ""


def trova_crp(email: str, cognome: str, nome: str):
    """Cerca Socio(capo) per email, poi per nome/cognome univoco.

    Restituisce (socio, trovato). L'import capi va eseguito prima.
    """
    if email:
        try:
            return Socio.objects.get(email__iexact=email, categoria=Categoria.CAPO), True
        except Socio.DoesNotExist:
            pass
    if cognome:
        qs = Socio.objects.filter(cognome__iexact=cognome, categoria=Categoria.CAPO)
        if nome:
            qs = qs.filter(nome__iexact=nome)
        if qs.count() == 1:
            return qs.first(), True
    return None, False


def _get_or_create_squadriglia(zona_nome, gruppo_nome, reparto_nome, sq_nome):
    zona, gruppo = _get_or_create_zona_gruppo(zona_nome, gruppo_nome)
    reparto, _ = Reparto.objects.get_or_create(nome=reparto_nome, gruppo=gruppo)
    squadriglia, _ = Squadriglia.objects.get_or_create(nome=sq_nome, reparto=reparto)
    return squadriglia


def _crea_crp_provvisorio(email: str, cognome: str, nome: str, zona, gruppo):
    """Crea un Socio(capo, provvisorio) con codice tmp quando il CRP non è in DB.

    Il codice tmpNNNNN identifica il record come provvisorio e verrà sostituito
    con il codice socio reale durante la riconciliazione.
    """
    from apps.org.models import Socio
    if email:
        existing = Socio.objects.filter(email__iexact=email, provvisorio=True).first()
        if existing:
            return existing
    codice_tmp = Socio.genera_codice_tmp()
    return Socio.objects.create(
        codice_socio=codice_tmp,
        nome=nome,
        cognome=cognome,
        email=email,
        categoria=Categoria.CAPO,
        zona=zona,
        gruppo=gruppo,
        provvisorio=True,
    )


class Command(BaseCommand):
    help = "Importa le squadriglie iscritte. Eseguire DOPO import_coca."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--edizione", type=int, required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        path: str = opts["path"]
        edizione_pk: int = opts["edizione"]
        dry_run: bool = opts["dry_run"]

        from apps.editions.models import Edizione
        try:
            edizione = Edizione.objects.get(pk=edizione_pk)
        except Edizione.DoesNotExist:
            raise CommandError(f"Edizione {edizione_pk} non trovata.")

        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f, delimiter=";"))
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        log = LogImportazione(
            tipo=TipoImport.SQUADRIGLIE,
            file_nome=path,
            edizione=edizione,
        )
        ok = scartati = da_riconciliare = 0
        riga_objs: list[RigaImportazione] = []

        with transaction.atomic():
            if not dry_run:
                log.save()

            for i, row in enumerate(rows, 1):
                codice_csq = _clean(row.get("Codice", ""))
                nome_csq = _clean(row.get("Nome", ""))
                cognome_csq = _clean(row.get("Cognome", ""))
                email_csq = _clean(row.get("Indirizzo mail capo squadriglia", ""))

                if not codice_csq or not codice_csq.isdigit() or not (4 <= len(codice_csq) <= 8):
                    scartati += 1
                    if not dry_run:
                        riga_objs.append(RigaImportazione(
                            log=log, numero=i, dati_grezzi=dict(row),
                            stato_match=StatoMatch.SCARTATA,
                            note="Codice CSQ non valido",
                        ))
                    continue

                crp_raw = _clean(row.get("NomeReferente", ""))
                crp_email = _clean(row.get("EmailReferente", ""))
                crp_cognome, crp_nome = _parse_crp_nome(crp_raw) if crp_raw else ("", "")

                zona_nome = _clean(row.get("Zona", "")) or "Sconosciuta"
                gruppo_nome = _clean(row.get("Gruppo", "")) or "Sconosciuto"
                reparto_nome = _clean(row.get("Reparto", "")) or "Reparto"
                sq_nome = _clean(row.get("Squadriglia", "")) or cognome_csq or "Squadriglia"
                tipo_riconferma = row.get(
                    "E' una riconferma? (indicare sì se si tratta di una riconferma)", ""
                ).strip().lower() in SI
                specialita = _clean(row.get("Specialita", "") or row.get("Specialità", ""))

                if not dry_run:
                    zona, gruppo = _get_or_create_zona_gruppo(zona_nome, gruppo_nome)
                    squadriglia = _get_or_create_squadriglia(
                        zona_nome, gruppo_nome, reparto_nome, sq_nome
                    )
                    csq, _ = Socio.objects.update_or_create(
                        codice_socio=codice_csq,
                        defaults={
                            "nome": nome_csq,
                            "cognome": cognome_csq,
                            "categoria": Categoria.RAGAZZO,
                            "zona": zona,
                            "gruppo": gruppo,
                            **({"email": email_csq} if email_csq else {}),
                        },
                    )

                    crp_socio, crp_trovato = trova_crp(crp_email, crp_cognome, crp_nome)

                    if not crp_trovato and (crp_email or crp_cognome):
                        # Crea un CRP provvisorio con i dati disponibili (email e nome
                        # dal tracciato Evento sono certificati, manca solo il codice socio).
                        # Verrà sostituito dalla riconciliazione manuale o automatica.
                        crp_socio = _crea_crp_provvisorio(
                            crp_email, crp_cognome, crp_nome, zona, gruppo
                        )

                    from apps.diaries.models import Anagrafica, Diario, TipoDiario
                    diario, _ = Diario.objects.get_or_create(
                        edizione=edizione,
                        squadriglia=squadriglia,
                        defaults={
                            "csq": csq,
                            "crp": crp_socio,
                            "tipo": TipoDiario.RINNOVO if tipo_riconferma else TipoDiario.NUOVO,
                        },
                    )
                    Anagrafica.objects.get_or_create(
                        diario=diario,
                        defaults={"specialita": specialita},
                    )

                    if crp_trovato:
                        stato_riga = StatoMatch.OK
                        note_riga = ""
                        ok += 1
                    elif crp_socio:
                        stato_riga = StatoMatch.DA_RICONCILIARE
                        note_riga = (
                            f"CRP provvisorio creato — email: {crp_email or '—'}, "
                            f"nome: {crp_raw or '—'}. Codice socio da riconciliare."
                        )
                        da_riconciliare += 1
                    else:
                        stato_riga = StatoMatch.DA_RICONCILIARE
                        note_riga = "CRP non trovato e dati insufficienti per crearlo."
                        da_riconciliare += 1

                    riga_objs.append(RigaImportazione(
                        log=log, numero=i, dati_grezzi=dict(row),
                        stato_match=stato_riga,
                        socio_match=crp_socio,
                        note=note_riga,
                    ))
                else:
                    ok += 1

            if not dry_run:
                RigaImportazione.objects.bulk_create(riga_objs)
                log.totale = ok + da_riconciliare + scartati
                log.ok = ok
                log.scartati = scartati
                log.da_riconciliare = da_riconciliare
                log.save(update_fields=["totale", "ok", "scartati", "da_riconciliare"])

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY-RUN] ' if dry_run else ''}"
            f"Squadriglie: {ok} ok, {da_riconciliare} anomalie CRP, {scartati} scartate."
        ))
