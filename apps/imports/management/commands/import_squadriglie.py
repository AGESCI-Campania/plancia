# apps/imports/management/commands/import_squadriglie.py
"""Import squadriglie iscritte dal tracciato Evento (Appendice D.1).

L'import capi (Co.Ca.) deve essere eseguito PRIMA di questo, perché il CRP
viene cercato per email tra i Socio(capo) già presenti. Le righe senza match
CRP vengono salvate come 'da_riconciliare' e possono essere riproposte in
seguito senza re-importare il file, ad esempio dopo un nuovo import capi o
l'inserimento manuale del capo (pulsante "Riprova anomalie" nella UI).

Formato CSV atteso: UTF-8 con BOM, separatore ';'.
La prima riga contiene l'ID evento (es. "Evento24139") — viene saltata.
La seconda riga contiene le intestazioni di colonna.
- CSQ: Codice + Cognome + Nome → upsert Socio(ragazzo); email aggiornata se presente.
  Se il Codice è assente/non valido, viene creato un Socio(ragazzo, provvisorio=True)
  con codice tmpNNNNN; la riga è marcata DA_RICONCILIARE.
- CRP: match Socio(capo) per email (EmailReferente); fallback per nome/cognome.
- Colonne: "Nome squadriglia", "Nome reparto", "Specialità di squadriglia".
- Crea Diario + Anagrafica; tipo = rinnovo se "E' una riconferma?" == sì.

Uso: uv run python manage.py import_squadriglie path/al/file.csv --edizione <pk> [--dry-run]
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch, TipoImport
from apps.org.models import Categoria, Reparto, Socio, Squadriglia

from .import_coca import _clean, _get_or_create_zona_gruppo, leggi_csv

logger = logging.getLogger(__name__)

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
    Se l'email è duplicata nel DB, prova a raffinare per nome/cognome;
    altrimenti prende il primo record trovato.
    """
    if email:
        qs_email = Socio.objects.filter(email__iexact=email, categoria=Categoria.CAPO)
        count = qs_email.count()
        if count == 1:
            return qs_email.first(), True
        if count > 1:
            # Email duplicata: prova a restringere per nome/cognome
            narrowed = qs_email
            if cognome:
                narrowed = narrowed.filter(cognome__iexact=cognome)
            if nome:
                narrowed = narrowed.filter(nome__iexact=nome)
            match = narrowed.first() or qs_email.first()
            logger.warning(
                "Email CRP duplicata (%s): trovati %d Socio, usato %s", email, count, match
            )
            return match, True
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
    """Crea un Socio(capo, provvisorio) con codice tmp quando il CRP non è in DB."""
    if email:
        existing = Socio.objects.filter(email__iexact=email, provvisorio=True, categoria=Categoria.CAPO).first()
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


def _crea_csq_provvisorio(cognome: str, nome: str, email: str, zona, gruppo):
    """Crea un Socio(ragazzo, provvisorio) con codice tmp quando il codice CSQ è assente."""
    if email:
        existing = Socio.objects.filter(
            email__iexact=email, provvisorio=True, categoria=Categoria.RAGAZZO
        ).first()
        if existing:
            return existing
    codice_tmp = Socio.genera_codice_tmp()
    return Socio.objects.create(
        codice_socio=codice_tmp,
        nome=nome,
        cognome=cognome,
        email=email,
        categoria=Categoria.RAGAZZO,
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

        from apps.diaries.models import Anagrafica, Diario, TipoDiario
        from apps.editions.models import Edizione

        try:
            edizione = Edizione.objects.get(pk=edizione_pk)
        except Edizione.DoesNotExist as exc:
            raise CommandError(f"Edizione {edizione_pk} non trovata.") from exc

        try:
            rows = leggi_csv(path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        log = LogImportazione(
            tipo=TipoImport.SQUADRIGLIE,
            file_nome=path,
            edizione=edizione,
        )
        ok = scartati = da_riconciliare = 0
        riga_objs: list[RigaImportazione] = []

        if not dry_run:
            log.save()

        try:
            with transaction.atomic():
                for i, row in enumerate(rows, 1):
                    dati_grezzi = {k: (str(v) if v is not None else "") for k, v in row.items()}
                    codice_csq = _clean(row.get("Codice", ""))
                    nome_csq = _clean(row.get("Nome", ""))
                    cognome_csq = _clean(row.get("Cognome", ""))
                    email_csq = _clean(row.get("Indirizzo mail capo squadriglia", ""))

                    codice_valido = codice_csq and codice_csq.isdigit() and (4 <= len(codice_csq) <= 8)

                    crp_raw = _clean(row.get("NomeReferente", ""))
                    crp_email = _clean(row.get("EmailReferente", ""))
                    crp_cognome, crp_nome = _parse_crp_nome(crp_raw) if crp_raw else ("", "")

                    zona_nome = _clean(row.get("Zona", "")) or "Sconosciuta"
                    gruppo_nome = _clean(row.get("Gruppo", "")) or "Sconosciuto"
                    reparto_nome = (
                        _clean(row.get("Nome reparto", "") or row.get("Reparto", "")) or "Reparto"
                    )
                    sq_nome = (
                        _clean(row.get("Nome squadriglia", "") or row.get("Squadriglia", ""))
                        or cognome_csq or "Squadriglia"
                    )
                    tipo_riconferma = row.get(
                        "E' una riconferma? (indicare sì se si tratta di una riconferma)", ""
                    ).strip().lower() in SI
                    specialita = _clean(
                        row.get("Specialità di squadriglia", "")
                        or row.get("Specialita", "")
                        or row.get("Specialità", "")
                    )

                    if not dry_run:
                        sp = transaction.savepoint()
                        try:
                            zona, gruppo = _get_or_create_zona_gruppo(zona_nome, gruppo_nome)
                            squadriglia = _get_or_create_squadriglia(
                                zona_nome, gruppo_nome, reparto_nome, sq_nome
                            )

                            if codice_valido:
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
                                csq_provvisorio = False
                            else:
                                # Codice assente o non valido: crea CSQ provvisorio
                                csq = _crea_csq_provvisorio(cognome_csq, nome_csq, email_csq, zona, gruppo)
                                csq_provvisorio = True

                            crp_socio, crp_trovato = trova_crp(crp_email, crp_cognome, crp_nome)

                            if not crp_trovato and (crp_email or crp_cognome):
                                crp_socio = _crea_crp_provvisorio(
                                    crp_email, crp_cognome, crp_nome, zona, gruppo
                                )

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

                            transaction.savepoint_commit(sp)

                            # Crea gli account utente (password inutilizzabile;
                            # l'attivazione avviene via invito).
                            try:
                                from apps.notifications.service import (
                                    crea_o_ottieni_utente_per_socio,
                                )
                                crea_o_ottieni_utente_per_socio(csq, "csq")
                                if crp_socio and not getattr(crp_socio, "provvisorio", False):
                                    crea_o_ottieni_utente_per_socio(crp_socio, "crp")
                            except Exception as exc_u:
                                logger.warning("Creazione utenti riga %d: %s", i, exc_u)

                            if csq_provvisorio:
                                stato_riga = StatoMatch.DA_RICONCILIARE
                                note_riga = (
                                    f"CSQ provvisorio creato (codice assente) — "
                                    f"{cognome_csq} {nome_csq}, email: {email_csq or '—'}. "
                                    "Codice socio da riconciliare."
                                )
                                da_riconciliare += 1
                            elif crp_trovato:
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
                                log=log, numero=i, dati_grezzi=dati_grezzi,
                                stato_match=stato_riga,
                                socio_match=crp_socio,
                                note=note_riga,
                            ))

                        except Exception as exc:
                            transaction.savepoint_rollback(sp)
                            scartati += 1
                            logger.warning(
                                "Squadriglie riga %d (codice CSQ %s): %s", i, codice_csq, exc
                            )
                            riga_objs.append(RigaImportazione(
                                log=log, numero=i, dati_grezzi=dati_grezzi,
                                stato_match=StatoMatch.SCARTATA,
                                note=str(exc)[:255],
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

        except Exception as exc:
            if not dry_run:
                log.scartati = scartati
                log.totale = ok + da_riconciliare + scartati
                log.da_riconciliare = da_riconciliare
                log.save(update_fields=["totale", "ok", "scartati", "da_riconciliare"])
            raise CommandError(f"Errore durante l'import: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY-RUN] ' if dry_run else ''}"
            f"Squadriglie: {ok} ok, {da_riconciliare} anomalie CRP, {scartati} scartate."
        ))
