"""`manage.py popola_demo --password …` — dati dimostrativi SINTETICI per sviluppo e manuale.

Crea (o aggiorna) un'edizione dei Guidoncini Verdi con zone, gruppi, reparti, squadriglie e
soci inventati, un utente per ogni ruolo, diari in tutti gli stati principali con i moduli
compilati, qualche foto generata, valutazioni, assegnazioni alla Pattuglia GV, inviti,
ticket helpdesk e uno storico di import. Serve a provare l'app e a rigenerare gli screenshot
del manuale (`frontend/scripts/schermate-manuale.ts`).

Idempotente: rieseguito non duplica nulla; aggiorna le password degli utenti demo e lascia
com'è lo stato dei diari già creati (con `--ricrea` li cancella e li ricrea da capo).
Lo staff (Admin, Segreteria, Incaricato EG) ha il TOTP già configurato: in sviluppo si entra
con il codice di bypass `MFA_TOTP_INSECURE_BYPASS_CODE` (`000000`, `config/settings/dev.py`).

Niente dati reali: nomi, codici socio (99xxxx) ed email (@example.org) sono inventati.
Rifiuta di girare con DEBUG=False se non si passa `--consenti-senza-debug`.
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

PASSWORD_ENV = "PLANCIA_DEMO_PASSWORD"
DOMINIO = "example.org"
# Token fisso dell'invito non ancora usato (pagina di attivazione negli screenshot)
TOKEN_INVITO_DEMO = uuid.UUID("5e1f0c2a-7d1b-4c55-9a7e-2b6f3f1d0a01")

ZONE = {
    "Zona Partenope": {"Partenope 1": ["Orsa Maggiore", "Stella Polare"]},
    "Zona Irpinia": {"Irpinia 2": ["Aquila Reale"]},
}

# (squadriglia, reparto, codice socio del Capo Squadriglia, nome, cognome, tipo, stato, specialità)
SQUADRIGLIE = [
    ("Pantere", "Orsa Maggiore", "990101", "Giulia", "Esposito", "nuovo", "in_compilazione", "Campismo"),
    ("Aquile", "Orsa Maggiore", "990102", "Marco", "Russo", "nuovo", "relazione_finale", "Esplorazione"),
    ("Volpi", "Orsa Maggiore", "990103", "Sara", "Romano", "rinnovo", "approvato", "Natura"),
    ("Gabbiani", "Orsa Maggiore", "990104", "Luca", "Ferrara", "rinnovo", "non_iniziato", "Nautica"),
    ("Castori", "Stella Polare", "990105", "Chiara", "Colombo", "nuovo", "inviato", "Artigianato"),
    ("Falchi", "Stella Polare", "990106", "Davide", "Ricci", "nuovo", "in_valutazione", "Pronto Intervento"),
    ("Lupi", "Aquila Reale", "990107", "Martina", "Marino", "nuovo", "in_revisione", "Alpinismo"),
    ("Cervi", "Aquila Reale", "990108", "Andrea", "Greco", "rinnovo", "maggiori_info", "Espressione"),
]

# Capi: (chiave, codice socio, nome, cognome, gruppo, ruolo, reparto di cui è Capo Reparto)
CAPI = [
    ("crp", "990201", "Paolo", "De Luca", "Partenope 1", "crp", "Orsa Maggiore"),
    ("crp2", "990202", "Anna", "Gallo", "Partenope 1", "crp", "Stella Polare"),
    ("crp3", "990203", "Roberto", "Conti", "Irpinia 2", "crp", "Aquila Reale"),
    ("pgv", "990204", "Elena", "Mancini", "Partenope 1", "pgv", None),
    ("segreteria", "990205", "Francesca", "Costa", "Partenope 1", "segreteria", None),
    ("incaricato", "990206", "Stefano", "Fontana", "Irpinia 2", "incaricato_eg", None),
]

STATI_CON_RELAZIONE = {
    "relazione_finale", "inviato", "in_valutazione", "in_revisione", "approvato", "maggiori_info",
}
STATI_INVIATI = {"inviato", "in_valutazione", "in_revisione", "approvato", "maggiori_info"}


class Command(BaseCommand):
    help = "Crea dati dimostrativi sintetici (edizione, diari, utenti per ogni ruolo). Idempotente."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--password", default=None,
            help=f"Password degli utenti demo (oppure variabile d'ambiente {PASSWORD_ENV}).",
        )
        parser.add_argument("--anno", type=int, default=None, help="Anno dell'edizione (default: anno prossimo).")
        parser.add_argument("--ricrea", action="store_true", help="Cancella e ricrea i diari demo.")
        parser.add_argument(
            "--disattiva-rate-limit", action="store_true",
            help="Disattiva il rate limit dell'API (utile per gli script Playwright).",
        )
        parser.add_argument(
            "--consenti-senza-debug", action="store_true",
            help="Permette l'esecuzione con DEBUG=False (sconsigliato: mai in produzione).",
        )

    def handle(self, *args, **opzioni) -> None:
        if not settings.DEBUG and not opzioni["consenti_senza_debug"]:
            raise CommandError("popola_demo crea utenti con password nota: solo in sviluppo (DEBUG=True).")
        password = opzioni["password"] or os.environ.get(PASSWORD_ENV, "")
        if len(password) < 8:
            raise CommandError(f"Serve una password di almeno 8 caratteri (--password o {PASSWORD_ENV}).")
        anno = opzioni["anno"] or timezone.now().year + 1

        with transaction.atomic():
            self.password = password
            edizione = self._edizione(anno)
            reparti = self._organizzazione()
            utenti, soci_capi = self._utenti_staff_e_capi(reparti)
            soci_csq = self._soci_csq(reparti)
            utenti["csq"] = self._utente_socio(soci_csq["Pantere"], "csq", f"csq@{DOMINIO}")
            self._nomina(utenti["csq"], "csq", edizione=edizione)
            if opzioni["ricrea"]:
                self._cancella_diari(edizione)
            diari = self._diari(edizione, reparti, soci_csq, soci_capi, utenti)
            self._inviti(edizione, diari, soci_csq, utenti)
            self._ticket(utenti, diari)
            self._import(edizione, utenti["segreteria"])
            if opzioni["disattiva_rate_limit"]:
                self._disattiva_rate_limit()

        self.stdout.write(self.style.SUCCESS(f"Dati demo pronti: edizione {anno}, {len(diari)} diari."))
        self.stdout.write("Utenti (stessa password per tutti; staff con TOTP: codice 000000 in sviluppo):")
        for chiave in ("admin", "segreteria", "incaricato", "pgv", "crp", "csq"):
            u = utenti[chiave]
            accesso = u.username if chiave == "csq" else u.email
            self.stdout.write(f"  {chiave:<11} {accesso}")
        self.stdout.write(f"Invito da attivare: /invito/{TOKEN_INVITO_DEMO}")

    # --- Edizione e organizzazione -------------------------------------------------

    def _edizione(self, anno: int):
        from apps.editions.models import Edizione, StatoEdizione

        edizione, _ = Edizione.objects.update_or_create(
            anno=anno,
            defaults={
                "stato": StatoEdizione.APERTA,
                "scadenza_evento": date(anno, 4, 30),
                "scadenza_assemblea": date(anno, 9, 30),
                "data_evento_inizio": date(anno, 5, 22),
                "data_evento_fine": date(anno, 5, 24),
                "evento_comune": "Montella",
                "evento_localita": "Base scout del Monte Demo",
            },
        )
        return edizione

    def _organizzazione(self) -> dict:
        from apps.org.models import Gruppo, Reparto, Zona

        reparti = {}
        for nome_zona, gruppi in ZONE.items():
            zona, _ = Zona.objects.get_or_create(nome=nome_zona)
            for nome_gruppo, nomi_reparti in gruppi.items():
                gruppo, _ = Gruppo.objects.get_or_create(nome=nome_gruppo, zona=zona)
                for nome in nomi_reparti:
                    reparti[nome], _ = Reparto.objects.get_or_create(nome=f"Reparto {nome}", gruppo=gruppo)
        return reparti

    def _socio(self, codice: str, nome: str, cognome: str, categoria: str, gruppo, email: str = ""):
        from apps.org.models import Socio

        socio, _ = Socio.objects.update_or_create(
            codice_socio=codice,
            defaults={
                "nome": nome, "cognome": cognome, "categoria": categoria, "email": email,
                "gruppo": gruppo, "zona": gruppo.zona, "cellulare": f"333 {codice[-4:]}000",
            },
        )
        return socio

    def _utenti_staff_e_capi(self, reparti: dict):
        from apps.org.models import Gruppo

        utenti = {"admin": self._utente_staff("admin", "Admin", "Demo", "admin")}
        soci_capi = {}
        for chiave, codice, nome, cognome, nome_gruppo, ruolo, _reparto in CAPI:
            gruppo = Gruppo.objects.get(nome=nome_gruppo)
            email = f"{chiave}@{DOMINIO}"
            socio = self._socio(codice, nome, cognome, "capo", gruppo, email)
            soci_capi[chiave] = socio
            utenti[chiave] = self._utente_socio(socio, ruolo, email)
            self._nomina(utenti[chiave], ruolo)
        for chiave in ("admin", "segreteria", "incaricato"):
            self._totp(utenti[chiave])
        return utenti, soci_capi

    def _soci_csq(self, reparti: dict) -> dict:
        return {
            sq: self._socio(codice, nome, cognome, "ragazzo", reparti[rep].gruppo)
            for sq, rep, codice, nome, cognome, *_ in SQUADRIGLIE
        }

    # --- Utenti -------------------------------------------------------------------

    def _utente_staff(self, chiave: str, nome: str, cognome: str, ruolo: str):
        from apps.accounts.models import User

        email = f"{chiave}@{DOMINIO}"
        utente, _ = User.objects.update_or_create(
            email=email,
            defaults={
                "username": email, "first_name": nome, "last_name": cognome, "ruolo": ruolo,
                "is_active": True, "is_staff": ruolo == "admin", "is_superuser": ruolo == "admin",
            },
        )
        self._credenziali(utente)
        self._nomina(utente, ruolo)
        return utente

    def _utente_socio(self, socio, ruolo: str, email: str):
        """Come `crea_o_ottieni_utente_per_socio`: username = codice socio."""
        from apps.accounts.models import User

        utente, _ = User.objects.update_or_create(
            username=socio.codice_socio,
            defaults={
                "email": email, "first_name": socio.nome, "last_name": socio.cognome,
                "ruolo": ruolo, "socio": socio, "is_active": True,
            },
        )
        self._credenziali(utente)
        return utente

    def _credenziali(self, utente) -> None:
        from allauth.account.models import EmailAddress

        utente.set_password(self.password)
        utente.save()
        EmailAddress.objects.filter(user=utente).exclude(email=utente.email).delete()
        EmailAddress.objects.update_or_create(
            user=utente, email=utente.email, defaults={"verified": True, "primary": True}
        )

    def _nomina(self, utente, ruolo: str, edizione=None) -> None:
        from apps.accounts.models import Nomina

        Nomina.objects.get_or_create(
            utente=utente, ruolo=ruolo, attiva=True,
            defaults={"socio": utente.socio, "edizione": edizione},
        )

    def _totp(self, utente) -> None:
        from allauth.mfa.models import Authenticator

        Authenticator.objects.get_or_create(
            user=utente, type=Authenticator.Type.TOTP, defaults={"data": {"secret": "JBSWY3DPEHPK3PXP"}}
        )

    # --- Diari --------------------------------------------------------------------

    def _cancella_diari(self, edizione) -> None:
        for diario in edizione.diari.all():
            for allegato in diario.allegati.all():
                if allegato.file:
                    allegato.file.delete(save=False)
            diario.delete()

    def _diari(self, edizione, reparti, soci_csq, soci_capi, utenti) -> list:
        from apps.diaries.models import Diario, ScadenzaRiferimento
        from apps.org.models import Squadriglia

        crp_di = {rep: soci_capi[chiave] for chiave, *_, rep in CAPI if rep}
        diari = []
        for nome, rep, _cod, _n, _c, tipo, stato, specialita in SQUADRIGLIE:
            squadriglia, _ = Squadriglia.objects.get_or_create(nome=nome, reparto=reparti[rep])
            diario, creato = Diario.objects.get_or_create(
                edizione=edizione, squadriglia=squadriglia,
                defaults={
                    "csq": soci_csq[nome], "crp": crp_di[rep], "tipo": tipo, "stato": stato,
                    "scadenza_riferimento": ScadenzaRiferimento.PRIMA,
                },
            )
            if creato:
                self._compila(diario, stato, specialita, utenti)
            diari.append(diario)
        return diari

    def _compila(self, diario, stato: str, specialita: str, utenti) -> None:
        from apps.editions.models import Dilazione

        adesso = timezone.now()
        if stato == "non_iniziato":
            self._anagrafica(diario, specialita)  # precompilata dall'import squadriglie
            Dilazione.objects.create(
                diario=diario, nuova_scadenza=diario.edizione.scadenza_evento + timedelta(days=14),
                motivazione="Campo estivo del reparto durante la prima scadenza.",
                concessa_da=utenti["segreteria"],
            )
            return
        self._anagrafica(diario, specialita)
        self._presentazione(diario)
        self._impresa(diario, 1, utenti)
        if diario.tipo == "nuovo" or stato != "in_compilazione":
            self._impresa(diario, 2, utenti)
            self._missione(diario, utenti)
        if stato in STATI_CON_RELAZIONE:
            diario.csq_completato_at = adesso - timedelta(days=20)
            self._relazione(diario, completa=stato != "relazione_finale")
        if stato in STATI_INVIATI:
            diario.inviato_at = adesso - timedelta(days=10)
        diario.save()
        self._valutazione(diario, stato, utenti)

    def _anagrafica(self, diario, specialita: str) -> None:
        from apps.diaries.models import Anagrafica

        crp, csq = diario.crp, diario.csq
        Anagrafica.objects.update_or_create(
            diario=diario,
            defaults={
                "crp_nome": crp.nome, "crp_cognome": crp.cognome, "crp_email": crp.email,
                "crp_cell": crp.cellulare, "csq_nome": csq.nome, "csq_cognome": csq.cognome,
                "csq_email": "", "csq_cell": "", "specialita": specialita, "partecipa_evento": True,
                "desc_prima_impresa": "Costruire un rifugio per il campo di primavera.",
                "desc_seconda_impresa": "Organizzare un'uscita di orientamento per il reparto.",
                "tecniche": "Pionieristica, topografia, cucina trapper.",
            },
        )

    def _presentazione(self, diario) -> None:
        from apps.diaries.models import MembroSq, Presentazione

        pres, _ = Presentazione.objects.update_or_create(
            diario=diario,
            defaults={"cosa_sappiamo_fare": (
                "Siamo una squadriglia affiatata: ci piace stare all'aperto, montare tende e "
                "cucinare al campo. Sappiamo leggere la carta topografica e usare la bussola; "
                "due di noi suonano la chitarra e animano i fuochi di bivacco."
            )},
        )
        pres.membri.all().delete()
        csq = diario.csq
        membri = [
            (f"{csq.nome} {csq.cognome}", "csq", "responsabilita"),
            ("Tommaso Bruno", "vcsq", "competenza"),
            ("Alice Rinaldi", "squadrigliere", "competenza"),
            ("Pietro Caruso", "squadrigliere", "scoperta"),
            ("Viola Moretti", "squadrigliere", "scoperta"),
        ]
        for nome, ruolo, sentiero in membri:
            MembroSq.objects.create(presentazione=pres, nome=nome, ruolo=ruolo, sentiero=sentiero)

    def _impresa(self, diario, numero: int, utenti) -> None:
        from apps.diaries.models import EsitoSpecialita, Impresa, PostoAzione

        anno = diario.edizione.anno - 1
        titoli = {1: "Un rifugio nel bosco", 2: "Caccia al tesoro con la bussola"}
        impresa, _ = Impresa.objects.update_or_create(
            diario=diario, numero=numero,
            defaults={
                "titolo": titoli[numero],
                "data_inizio": date(anno, 10 + numero, 5),
                "data_fine": date(anno, 10 + numero, 26),
                "perche": "Volevamo un posto nostro dove ritrovarci durante le uscite e mettere "
                          "alla prova le tecniche di pionieristica imparate al campo estivo.",
                "come": "Abbiamo progettato il lavoro in tre riunioni, chiesto consiglio a un "
                        "falegname e diviso i posti d'azione secondo le competenze di ciascuno.",
                "cosa": "In tre uscite abbiamo costruito la struttura con pali e legature, "
                        "coperto il tetto con teli impermeabili e preparato un angolo cucina.",
                "link_esterno": "https://example.org/video-impresa",
            },
        )
        impresa.posti_azione.all().delete()
        impresa.esiti_specialita.all().delete()
        for chi, cosa in [("Tommaso Bruno", "Progettista"), ("Alice Rinaldi", "Cambusiera"),
                          ("Pietro Caruso", "Fotografo")]:
            PostoAzione.objects.create(impresa=impresa, chi=chi, cosa=cosa)
        EsitoSpecialita.objects.create(impresa=impresa, tipo="specialita", chi="Alice Rinaldi",
                                       nome="Cuoco", stato="conquistata")
        EsitoSpecialita.objects.create(impresa=impresa, tipo="specialita", chi="Pietro Caruso",
                                       nome="Fotografo", stato="in_cammino")
        EsitoSpecialita.objects.create(impresa=impresa, tipo="brevetto", chi="Tommaso Bruno",
                                       nome="Pioniere", stato="in_cammino")
        self._foto(diario, f"impresa_{numero}", 3 if numero == 1 else 1, utenti)

    def _missione(self, diario, utenti) -> None:
        from apps.diaries.models import Missione

        Missione.objects.update_or_create(
            diario=diario,
            defaults={
                "titolo": "Il sentiero perduto",
                "data": date(diario.edizione.anno - 1, 12, 14),
                "descrizione_svolgimento": (
                    "Ci è stato chiesto di ritrovare e segnare un vecchio sentiero. Con carta e "
                    "bussola abbiamo individuato il tracciato, ripulito il passaggio e posato "
                    "i segnavia. La pioggia ci ha rallentato ma abbiamo finito prima del tramonto."
                ),
            },
        )
        self._foto(diario, "missione", 1, utenti)

    def _relazione(self, diario, completa: bool) -> None:
        from apps.diaries.models import RelazioneFinale

        RelazioneFinale.objects.update_or_create(
            diario=diario,
            defaults={
                "sintesi_impresa_1": "Impresa ben progettata e realizzata in tempi rispettati; "
                                     "tutti hanno avuto un posto d'azione.",
                "sintesi_impresa_2": "Buona organizzazione, qualche difficoltà nella preparazione "
                                     "dei percorsi." if completa else "",
                "sintesi_missione": "Missione svolta con impegno e spirito di adattamento."
                                    if completa else "",
                "considerazioni": "Le competenze acquisite sono state messe a servizio del reparto."
                                  if completa else "",
                "specialita_conquistata": True if completa else None,
            },
        )

    def _foto(self, diario, modulo: str, quante: int, utenti) -> None:
        from apps.diaries.models import Allegato

        colori = [((61, 142, 51), (190, 220, 120)), ((30, 90, 160), (150, 200, 240)),
                  ((170, 90, 30), (250, 210, 140))]
        for i in range(quante):
            contenuto = _immagine_demo(*colori[i % len(colori)], f"{diario.squadriglia.nome} · {i + 1}")
            nome = f"{modulo}_{i + 1}.jpg"
            allegato = Allegato(diario=diario, modulo=modulo, nome=nome, mime="image/jpeg",
                                dimensione=len(contenuto), caricato_da=utenti["csq"])
            allegato.file.save(nome, ContentFile(contenuto), save=False)
            allegato.save()

    def _valutazione(self, diario, stato: str, utenti) -> None:
        from apps.evaluations.models import AssegnazionePGV, StatoValutazione, Valutazione

        incaricato, pgv = utenti["incaricato"], utenti["pgv"]
        if stato in ("in_valutazione", "in_revisione"):
            val = Valutazione.objects.create(diario=diario, stato=StatoValutazione.ASSEGNATA)
            AssegnazionePGV.objects.create(valutazione=val, pgv=pgv, assegnato_da=incaricato)
            if stato == "in_revisione":
                val.valutatore, val.proposta_esito = pgv, "approvata"
                val.stato = StatoValutazione.IN_REVISIONE
                val.note = "Diario completo e ben documentato: proposta di approvazione."
                val.save()
        elif stato in ("approvato", "maggiori_info"):
            Valutazione.objects.create(
                diario=diario, stato=StatoValutazione.CONFERMATA, valutatore=incaricato,
                confermata_da=incaricato,
                esito="approvata" if stato == "approvato" else "maggiori_info",
                note="Complimenti alla squadriglia!" if stato == "approvato"
                else "Aggiungete qualche foto della missione e la descrizione dei posti d'azione.",
            )
            if stato == "approvato":
                diario.pubblicato_at = timezone.now() - timedelta(days=2)
                diario.save(update_fields=["pubblicato_at"])

    # --- Inviti, ticket, import ---------------------------------------------------

    def _inviti(self, edizione, diari, soci_csq, utenti) -> None:
        from apps.notifications.models import DeliveryStatus, Invito, StatoInvito, TipoInvito
        from apps.notifications.service import crea_o_ottieni_utente_per_socio

        adesso = timezone.now()
        for diario in diari:
            if diario.squadriglia.nome == "Cervi":
                continue  # resta "Non inviato" nella pagina Gestione inviti
            if not Invito.objects.filter(diario=diario, ruolo_target="crp").exists():
                crp = diario.crp.utente
                attivato = crp == utenti["crp"]
                Invito.objects.create(
                    diario=diario, utente=crp, ruolo_target="crp", tipo=TipoInvito.STANDARD,
                    stato=StatoInvito.ATTIVATO if attivato else StatoInvito.INVIATO,
                    attivato_at=adesso if attivato else None, delivery_status=DeliveryStatus.CONSEGNATO,
                )
            if not Invito.objects.filter(diario=diario, ruolo_target="csq").exists():
                nome = diario.squadriglia.nome
                utente = utenti["csq"] if nome == "Pantere" else crea_o_ottieni_utente_per_socio(soci_csq[nome], "csq")
                attivato = nome == "Pantere"
                Invito.objects.create(
                    diario=diario, utente=utente, ruolo_target="csq", tipo=TipoInvito.CODICE_SOCIO,
                    stato=StatoInvito.ATTIVATO if attivato else StatoInvito.INVIATO,
                    attivato_at=adesso if attivato else None,
                    token=TOKEN_INVITO_DEMO if nome == "Gabbiani" else uuid.uuid4(),
                    delivery_status=DeliveryStatus.INVIATO,
                )

    def _ticket(self, utenti, diari) -> None:
        from apps.helpdesk.models import RispostaTicket, Ticket

        pantere = next(d for d in diari if d.squadriglia.nome == "Pantere")
        t1, creato = Ticket.objects.get_or_create(
            oggetto="Non riesco a caricare le foto della missione",
            defaults={
                "aperto_da": utenti["csq"], "diario": pantere, "categoria": "tecnico",
                "corpo": "Quando scelgo le foto dal telefono resta tutto fermo. Come posso fare?",
            },
        )
        if creato:
            RispostaTicket.objects.create(
                ticket=t1, autore=utenti["segreteria"],
                testo="Ciao! Prova ad aggiornare l'app dal pulsante Aggiorna in fondo alla pagina "
                      "e riprova: le foto restano sul telefono finché non vengono inviate.",
            )
        t2, _ = Ticket.objects.get_or_create(
            oggetto="Richiesta di dilazione per la squadriglia Gabbiani",
            defaults={
                "aperto_da": utenti["crp"], "categoria": "dilazione", "stato": "in_lavorazione",
                "assegnato_a": utenti["segreteria"],
                "diario": next(d for d in diari if d.squadriglia.nome == "Gabbiani"),
                "corpo": "La squadriglia è al campo invernale fino a fine aprile: chiediamo due settimane in più.",
            },
        )
        # Con --ricrea i diari cambiano: i ticket restano e vanno ricollegati
        for ticket, squadriglia in ((t1, "Pantere"), (t2, "Gabbiani")):
            diario = next(d for d in diari if d.squadriglia.nome == squadriglia)
            if ticket.diario_id != diario.pk:
                ticket.diario = diario
                ticket.save(update_fields=["diario"])

    def _import(self, edizione, autore) -> None:
        from apps.imports.models import LogImportazione, RigaImportazione, StatoMatch

        log, creato = LogImportazione.objects.get_or_create(
            file_nome="squadriglie_iscritte_demo.csv",
            defaults={"tipo": "squadriglie", "edizione": edizione, "creato_da": autore,
                      "totale": len(SQUADRIGLIE) + 2, "ok": len(SQUADRIGLIE), "scartati": 1,
                      "da_riconciliare": 1},
        )
        if creato:
            for i, (sq, rep, codice, *_rest) in enumerate(SQUADRIGLIE, start=1):
                RigaImportazione.objects.create(
                    log=log, numero=i, stato_match=StatoMatch.OK,
                    dati_grezzi={"squadriglia": sq, "reparto": rep, "codice_socio_csq": codice},
                )
            RigaImportazione.objects.create(
                log=log, numero=len(SQUADRIGLIE) + 1, stato_match=StatoMatch.DA_RICONCILIARE,
                note="Capo Reparto non trovato per email: creato provvisorio",
                dati_grezzi={"squadriglia": "Delfini", "reparto": "Stella Polare",
                             "email_crp": f"capo.nuovo@{DOMINIO}"},
            )
            RigaImportazione.objects.create(
                log=log, numero=len(SQUADRIGLIE) + 2, stato_match=StatoMatch.SCARTATA,
                note="Codice socio del Capo Squadriglia mancante",
                dati_grezzi={"squadriglia": "Koala", "reparto": "Aquila Reale"},
            )
        LogImportazione.objects.get_or_create(
            file_nome="capi_coca_demo.csv",
            defaults={"tipo": "coca", "creato_da": autore, "totale": len(CAPI), "ok": len(CAPI)},
        )

    def _disattiva_rate_limit(self) -> None:
        from apps.siteconfig.models import Impostazioni

        imp = Impostazioni.get()
        Impostazioni.objects.filter(pk=imp.pk).update(api_ratelimit_abilitato=False)
        from django.core.cache import cache

        cache.delete(Impostazioni.CACHE_KEY)
        self.stdout.write("Rate limit API disattivato (riavvia Django se è già in esecuzione).")


def _immagine_demo(colore1: tuple, colore2: tuple, testo: str) -> bytes:
    """JPEG 1024×768 sintetico: sfumatura, colline stilizzate e una didascalia."""
    from PIL import Image, ImageDraw

    larghezza, altezza = 1024, 768
    img = Image.new("RGB", (larghezza, altezza), colore2)
    disegno = ImageDraw.Draw(img)
    for y in range(altezza):
        t = y / altezza
        disegno.line([(0, y), (larghezza, y)], fill=tuple(int(colore2[i] * (1 - t) + colore1[i] * t) for i in range(3)))
    disegno.ellipse((700, 80, 860, 240), fill=(255, 235, 150))
    disegno.polygon([(0, 768), (0, 520), (260, 380), (520, 560), (760, 420), (1024, 600), (1024, 768)],
                    fill=tuple(max(c - 40, 0) for c in colore1))
    disegno.polygon([(380, 620), (470, 470), (560, 620)], fill=(120, 70, 30))
    disegno.rectangle((0, 690, larghezza, 768), fill=(0, 0, 0))
    disegno.text((150, 712), f"Foto demo - {testo}", fill=(255, 255, 255), font_size=32)
    uscita = io.BytesIO()
    img.save(uscita, format="JPEG", quality=85)
    return uscita.getvalue()
