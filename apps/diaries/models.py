# apps/diaries/models.py
from django.db import models
from django.utils import timezone

# ---------------------------------------------------------------------------
# Costanti ufficiali del regolamento metodologico E/G (Allegati 2, 3, 4)
# ---------------------------------------------------------------------------

SPECIALITA_SQUADRIGLIA = [
    "Alpinismo", "Artigianato", "Campismo", "Civitas", "Esplorazione",
    "Espressione", "Giornalismo", "Internazionale", "Natura", "Nautica",
    "Olimpia", "Pronto Intervento",
]

SPECIALITA_INDIVIDUALI = [
    "Allevatore", "Alpinista", "Amico degli animali", "Amico del quartiere",
    "Archeologo", "Artigiano", "Artista di strada", "Astronomo", "Atleta",
    "Attore", "Battelliere", "Boscaiolo", "Botanico", "Campeggiatore",
    "Canoista", "Cantante", "Carpentiere navale", "Ciclista", "Collezionista",
    "Coltivatore", "Corrispondente", "Corrispondente radio", "Cuoco",
    "Danzatore", "Disegnatore", "Elettricista", "Elettronico",
    "Esperto del computer", "Europeista", "Falegname", "Fa tutto",
    "Folclorista", "Fotografo", "Geologo", "Giardiniere", "Giocattolaio",
    "Grafico", "Guida", "Guida marina", "Hebertista", "Idraulico",
    "Infermiere", "Interprete", "Lavoratore/ce in cuoio",
    "Maestro dei giochi", "Maestro dei nodi", "Meccanico", "Modellista",
    "Muratore", "Musicista", "Nuotatore", "Osservatore", "Osservatore meteo",
    "Pescatore", "Pompiere", "Redattore", "Regista", "Sarto", "Scenografo",
    "Segnalatore", "Servizio della Parola", "Servizio liturgico",
    "Servizio missionario", "Topografo", "Velista",
]

BREVETTI_COMPETENZA = [
    "Animatore sportivo", "Artista", "Cittadino del mondo",
    "Esploratore delle acque", "Giornalista", "Grafico multimediale",
    "Guida alpina", "Liturgista", "Maestro delle tecnologie", "Mani Abili",
    "Naturalista", "Pioniere", "Sherpa", "Soccorritore", "Trappeur",
]


class StatoDiario(models.TextChoices):
    NON_INIZIATO = "non_iniziato", "Non iniziato"
    IN_COMPILAZIONE = "in_compilazione", "In compilazione"
    RELAZIONE_FINALE = "relazione_finale", "Relazione finale"
    INVIATO = "inviato", "Inviato"
    IN_VALUTAZIONE = "in_valutazione", "In valutazione"
    IN_REVISIONE = "in_revisione", "In revisione"
    APPROVATO = "approvato", "Approvato"
    NON_APPROVATO = "non_approvato", "Non approvato"
    MAGGIORI_INFO = "maggiori_info", "Maggiori informazioni richieste"


class TipoDiario(models.TextChoices):
    NUOVO = "nuovo", "Nuovo"
    RINNOVO = "rinnovo", "Rinnovo"


class ScadenzaRiferimento(models.TextChoices):
    PRIMA = "prima", "Prima scadenza (evento)"
    SECONDA = "seconda", "Seconda scadenza (assemblea)"


# Transizioni ammesse per la FSM del Diario (docs sez. 6).
_TRANSIZIONI: dict[str, list[str]] = {
    StatoDiario.NON_INIZIATO: [StatoDiario.IN_COMPILAZIONE],
    StatoDiario.IN_COMPILAZIONE: [StatoDiario.RELAZIONE_FINALE],
    StatoDiario.RELAZIONE_FINALE: [StatoDiario.INVIATO],
    StatoDiario.INVIATO: [StatoDiario.IN_VALUTAZIONE],
    StatoDiario.IN_VALUTAZIONE: [
        StatoDiario.IN_REVISIONE,
        StatoDiario.APPROVATO,
        StatoDiario.NON_APPROVATO,
        StatoDiario.MAGGIORI_INFO,
    ],
    StatoDiario.IN_REVISIONE: [
        StatoDiario.APPROVATO,
        StatoDiario.NON_APPROVATO,
        StatoDiario.IN_VALUTAZIONE,
    ],
    StatoDiario.MAGGIORI_INFO: [StatoDiario.IN_COMPILAZIONE],
    StatoDiario.NON_APPROVATO: [StatoDiario.IN_COMPILAZIONE],
    StatoDiario.APPROVATO: [],
}


class Diario(models.Model):
    """Diario di Bordo di una Squadriglia per una Edizione. Vedi docs sez. 4 e 6."""

    edizione = models.ForeignKey(
        "editions.Edizione", on_delete=models.CASCADE, related_name="diari"
    )
    squadriglia = models.ForeignKey(
        "org.Squadriglia", on_delete=models.PROTECT, related_name="diari"
    )
    csq = models.ForeignKey(
        "org.Socio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="diari_csq",
        verbose_name="capo squadriglia",
        limit_choices_to={"categoria": "ragazzo"},
    )
    crp = models.ForeignKey(
        "org.Socio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="diari_crp",
        verbose_name="capo reparto",
        limit_choices_to={"categoria": "capo"},
    )
    tipo = models.CharField(
        max_length=10, choices=TipoDiario.choices, default=TipoDiario.NUOVO
    )
    stato = models.CharField(
        max_length=20, choices=StatoDiario.choices, default=StatoDiario.NON_INIZIATO, db_index=True
    )
    scadenza_riferimento = models.CharField(
        max_length=10,
        choices=ScadenzaRiferimento.choices,
        default=ScadenzaRiferimento.PRIMA,
    )
    pubblicato_at = models.DateTimeField(null=True, blank=True)
    csq_completato_at = models.DateTimeField(null=True, blank=True)
    inviato_at = models.DateTimeField(null=True, blank=True)
    creato_at = models.DateTimeField(auto_now_add=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    # Google Drive — sottocartelle univoche per questo diario (create da assicura_cartelle_diario)
    drive_folder_allegati_id = models.CharField(
        max_length=200, blank=True, verbose_name="ID cartella Drive allegati (diario)"
    )
    drive_folder_output_id = models.CharField(
        max_length=200, blank=True, verbose_name="ID cartella Drive output (diario)"
    )

    class Meta:
        unique_together = [("edizione", "squadriglia")]
        ordering = ["squadriglia__reparto__gruppo__zona__nome", "squadriglia__nome"]
        verbose_name = "diario"
        verbose_name_plural = "diari"

    def __str__(self) -> str:
        return f"{self.squadriglia} — {self.edizione}"

    # --- Helpers visibilità (docs sez. 5) -----------------------------------

    @property
    def moduli_csq_completi(self) -> bool:
        """True quando tutti i moduli obbligatori CSQ sono compilati.

        Entrambe le imprese (1ª e 2ª) sono obbligatorie per tutti i tipi.
        La missione è obbligatoria solo per tipo=NUOVO.
        """
        try:
            ana = self.anagrafica
        except Anagrafica.DoesNotExist:
            return False
        try:
            pres = self.presentazione
        except Presentazione.DoesNotExist:
            return False
        if not (ana and pres):
            return False
        if not self.imprese.filter(numero=1).exists():
            return False
        if not self.imprese.filter(numero=2).exists():
            return False
        if self.tipo == TipoDiario.NUOVO:
            return hasattr(self, "missione")
        return True

    @property
    def pubblicato(self) -> bool:
        return self.pubblicato_at is not None

    def scadenza_effettiva(self):
        """Restituisce la scadenza effettiva considerando eventuali dilazioni."""
        dilazione = self.dilazioni.order_by("-creata_at").first()
        if dilazione:
            return dilazione.nuova_scadenza
        ediz = self.edizione
        if self.scadenza_riferimento == ScadenzaRiferimento.PRIMA:
            return ediz.scadenza_evento
        return ediz.scadenza_assemblea

    def puo_essere_riaperto(self) -> bool:
        """Riapertura possibile solo se 1ª scadenza e 2ª non ancora passata (docs sez. 6 r.5)."""
        return (
            self.stato in (StatoDiario.NON_APPROVATO, StatoDiario.MAGGIORI_INFO)
            and self.scadenza_riferimento == ScadenzaRiferimento.PRIMA
            and not self.edizione.seconda_scadenza_passata
        )

    # --- Transizioni FSM (docs sez. 6) --------------------------------------

    def _transita(self, nuovo_stato: str) -> None:
        ammessi = _TRANSIZIONI.get(self.stato, [])
        if nuovo_stato not in ammessi:
            raise ValueError(
                f"Transizione {self.stato!r} → {nuovo_stato!r} non ammessa."
            )
        self.stato = nuovo_stato
        self.save()

    def inizia(self) -> None:
        """NON_INIZIATO → IN_COMPILAZIONE: il CSQ ha avviato la compilazione."""
        self._transita(StatoDiario.IN_COMPILAZIONE)
        self.save(update_fields=["stato"])

    def csq_invia(self) -> None:
        """IN_COMPILAZIONE → RELAZIONE_FINALE (CSQ completa la propria parte)."""
        self._transita(StatoDiario.RELAZIONE_FINALE)

    def invia(self) -> None:
        """RELAZIONE_FINALE → INVIATO (CRP invia il diario allo staff)."""
        self._transita(StatoDiario.INVIATO)
        self.inviato_at = timezone.now()
        self.save(update_fields=["inviato_at"])

    def avvia_valutazione(self) -> None:
        """INVIATO → IN_VALUTAZIONE."""
        self._transita(StatoDiario.IN_VALUTAZIONE)

    def proponi(self, esito: str) -> None:
        """IN_VALUTAZIONE → IN_REVISIONE (proposta PGV per Approvata/Non approvata)."""
        if esito not in (StatoDiario.APPROVATO, StatoDiario.NON_APPROVATO):
            raise ValueError("Proposta ammessa solo per Approvata/Non approvata.")
        self._transita(StatoDiario.IN_REVISIONE)

    def approva(self) -> None:
        """IN_VALUTAZIONE o IN_REVISIONE → APPROVATO."""
        self._transita(StatoDiario.APPROVATO)

    def respingi(self) -> None:
        """IN_VALUTAZIONE o IN_REVISIONE → NON_APPROVATO."""
        self._transita(StatoDiario.NON_APPROVATO)

    def richiedi_info(self) -> None:
        """IN_VALUTAZIONE → MAGGIORI_INFO."""
        self._transita(StatoDiario.MAGGIORI_INFO)

    def rigetta_proposta(self) -> None:
        """IN_REVISIONE → IN_VALUTAZIONE (Incaricato rigetta la proposta PGV)."""
        self._transita(StatoDiario.IN_VALUTAZIONE)

    def riapri(self) -> None:
        """NON_APPROVATO / MAGGIORI_INFO → IN_COMPILAZIONE (con guard riapertura)."""
        if not self.puo_essere_riaperto():
            raise ValueError("Riapertura non ammessa per questo diario.")
        self._transita(StatoDiario.IN_COMPILAZIONE)


# ---------------------------------------------------------------------------
# Modulo 1 — Anagrafica
# ---------------------------------------------------------------------------

class Anagrafica(models.Model):
    """Modulo 1: dati di squadriglia e referenti. Vedi docs sez. 5."""

    diario = models.OneToOneField(
        Diario, on_delete=models.CASCADE, related_name="anagrafica"
    )
    # Campi referente Capo Reparto (email solo staff)
    crp_nome = models.CharField(max_length=120, blank=True, verbose_name="nome Capo Reparto")
    crp_cognome = models.CharField(max_length=120, blank=True, verbose_name="cognome Capo Reparto")
    crp_email = models.EmailField(blank=True, verbose_name="email Capo Reparto")
    crp_cell = models.CharField(max_length=30, blank=True, verbose_name="cellulare Capo Reparto")

    # Campi referente Capo Squadriglia
    csq_nome = models.CharField(max_length=120, blank=True, verbose_name="nome Capo Squadriglia")
    csq_cognome = models.CharField(max_length=120, blank=True, verbose_name="cognome Capo Squadriglia")
    csq_email = models.EmailField(blank=True, verbose_name="email Capo Squadriglia")
    csq_cell = models.CharField(max_length=30, blank=True, verbose_name="cellulare Capo Squadriglia")

    # Specialità e partecipazione
    specialita = models.CharField(
        max_length=120, blank=True, verbose_name="specialità di squadriglia",
        choices=[("", "— Scegli —")] + [(s, s) for s in SPECIALITA_SQUADRIGLIA],
    )
    partecipa_evento = models.BooleanField(default=True, verbose_name="partecipa all'evento Guidoncini Verdi")

    # Precompilazione da import Evento (docs §14)
    desc_prima_impresa = models.TextField(blank=True, verbose_name="descrizione 1ª impresa (da import)")
    desc_seconda_impresa = models.TextField(blank=True, verbose_name="descrizione 2ª impresa (da import)")
    tecniche = models.TextField(blank=True, verbose_name="tecniche da acquisire (da import)")

    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "anagrafica"
        verbose_name_plural = "anagrafiche"

    def __str__(self) -> str:
        return f"Anagrafica — {self.diario}"


# ---------------------------------------------------------------------------
# Modulo 2 — Presentazione squadriglia
# ---------------------------------------------------------------------------

class Presentazione(models.Model):
    """Modulo 2: presentazione e composizione della squadriglia."""

    diario = models.OneToOneField(
        Diario, on_delete=models.CASCADE, related_name="presentazione"
    )
    cosa_sappiamo_fare = models.TextField(blank=True, verbose_name="cosa sappiamo fare")
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "presentazione squadriglia"
        verbose_name_plural = "presentazioni squadriglia"

    def __str__(self) -> str:
        return f"Presentazione — {self.diario}"


class SentieroCammino(models.TextChoices):
    SCOPERTA = "scoperta", "Scoperta"
    COMPETENZA = "competenza", "Competenza"
    RESPONSABILITA = "responsabilita", "Responsabilità"
    NON_SPECIFICATO = "non_specificato", "Non specificato"


class RuoloSq(models.TextChoices):
    CSQ = "csq", "Capo Squadriglia"
    VCSQ = "vcsq", "Vice Capo Squadriglia"
    SQUADRIGLIERE = "squadrigliere", "Squadrigliere"
    ALTRO = "altro", "Tutti gli altri"


class MembroSq(models.Model):
    """Membro della squadriglia con ruolo e tappa del sentiero."""

    presentazione = models.ForeignKey(
        Presentazione, on_delete=models.CASCADE, related_name="membri"
    )
    nome = models.CharField(max_length=120)
    cognome = models.CharField(max_length=60, blank=True, default="")
    ruolo = models.CharField(
        max_length=20, blank=True, verbose_name="ruolo in squadriglia",
        choices=RuoloSq.choices,
    )
    sentiero = models.CharField(
        max_length=20, choices=SentieroCammino.choices, default=SentieroCammino.NON_SPECIFICATO
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "membro squadriglia"
        verbose_name_plural = "membri squadriglia"

    def __str__(self) -> str:
        return self.nome


# ---------------------------------------------------------------------------
# Moduli 3/4 — Imprese
# ---------------------------------------------------------------------------

class TipoEsito(models.TextChoices):
    SPECIALITA = "specialita", "Specialità"
    BREVETTO = "brevetto", "Brevetto"


class StatoSpecialita(models.TextChoices):
    CONQUISTATA = "conquistata", "Conquistata"
    NON_CONQUISTATA = "non_conquistata", "Non conquistata"
    IN_CAMMINO = "in_cammino", "In cammino"


class Impresa(models.Model):
    """Modulo 3 (1ª impresa) o modulo 4 (2ª impresa). numero ∈ {1, 2}."""

    diario = models.ForeignKey(Diario, on_delete=models.CASCADE, related_name="imprese")
    numero = models.PositiveSmallIntegerField(choices=[(1, "1ª impresa"), (2, "2ª impresa")])
    titolo = models.CharField(max_length=200, blank=True)
    data_inizio = models.DateField(null=True, blank=True)
    data_fine = models.DateField(null=True, blank=True)
    perche = models.TextField(blank=True, verbose_name="perché")
    come = models.TextField(blank=True)
    cosa = models.TextField(blank=True)
    link_esterno = models.URLField(blank=True, verbose_name="link esterno (video/materiale)")
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("diario", "numero")]
        ordering = ["numero"]
        verbose_name = "impresa"
        verbose_name_plural = "imprese"

    def __str__(self) -> str:
        return f"{self.get_numero_display()} — {self.diario}"


class PostoAzione(models.Model):
    """Posto d'azione legato a un'impresa."""

    impresa = models.ForeignKey(Impresa, on_delete=models.CASCADE, related_name="posti_azione")
    chi = models.CharField(max_length=200, blank=True, verbose_name="chi")
    cosa = models.CharField(max_length=300, blank=True, verbose_name="cosa")
    # Mantenuto per compatibilità con i dati pre-migrazione; non più usato nell'UI
    descrizione = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        verbose_name = "posto d'azione"
        verbose_name_plural = "posti d'azione"

    def __str__(self) -> str:
        return f"{self.chi} — {self.cosa}"[:60] if self.chi or self.cosa else self.descrizione[:60]


class EsitoSpecialita(models.Model):
    """Specialità individuale o brevetto di competenza legato a un'impresa."""

    impresa = models.ForeignKey(
        Impresa, on_delete=models.CASCADE, related_name="esiti_specialita"
    )
    tipo = models.CharField(
        max_length=20, choices=TipoEsito.choices, default=TipoEsito.SPECIALITA,
        verbose_name="tipo",
    )
    chi = models.CharField(max_length=120, blank=True, verbose_name="chi")
    nome = models.CharField(max_length=120, verbose_name="nome")
    stato = models.CharField(
        max_length=20, choices=StatoSpecialita.choices, default=StatoSpecialita.IN_CAMMINO
    )

    class Meta:
        verbose_name = "esito specialità"
        verbose_name_plural = "esiti specialità"

    def __str__(self) -> str:
        return f"{self.nome} ({self.stato})"


# ---------------------------------------------------------------------------
# Modulo 5 — Missione
# ---------------------------------------------------------------------------

class Missione(models.Model):
    """Modulo 5: missione di squadriglia."""

    diario = models.OneToOneField(Diario, on_delete=models.CASCADE, related_name="missione")
    titolo = models.CharField(max_length=200, blank=True)
    data = models.DateField(null=True, blank=True)
    descrizione_svolgimento = models.TextField(blank=True)
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "missione"
        verbose_name_plural = "missioni"

    def __str__(self) -> str:
        return f"Missione — {self.diario}"


class PostoAzioneMissione(models.Model):
    missione = models.ForeignKey(Missione, on_delete=models.CASCADE, related_name="posti_azione")
    descrizione = models.CharField(max_length=300)

    class Meta:
        verbose_name = "posto d'azione (missione)"
        verbose_name_plural = "posti d'azione (missione)"

    def __str__(self) -> str:
        return self.descrizione[:60]


# ---------------------------------------------------------------------------
# Modulo 6 — Relazione finale CRP
# ---------------------------------------------------------------------------

class RelazioneFinale(models.Model):
    """Modulo 6: relazione del Capo Reparto. MAI visibile al CSQ (docs sez. 5)."""

    diario = models.OneToOneField(
        Diario, on_delete=models.CASCADE, related_name="relazione_finale"
    )
    sintesi_impresa_1 = models.TextField(blank=True, verbose_name="sintesi 1ª impresa")
    sintesi_impresa_2 = models.TextField(blank=True, verbose_name="sintesi 2ª impresa")
    sintesi_missione = models.TextField(blank=True, verbose_name="sintesi missione")
    considerazioni = models.TextField(blank=True, verbose_name="considerazioni finali")
    specialita_conquistata = models.BooleanField(
        null=True, blank=True, verbose_name="specialità conquistata"
    )
    aggiornato_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "relazione finale"
        verbose_name_plural = "relazioni finali"

    def __str__(self) -> str:
        return f"Relazione finale — {self.diario}"


# ---------------------------------------------------------------------------
# Allegati
# ---------------------------------------------------------------------------

class StatoSync(models.TextChoices):
    LOCALE = "locale", "Solo locale"
    IN_CODA = "in_coda", "In coda per l'upload"
    CARICATO = "caricato", "Caricato su Drive"


MODULO_FOTO_CHOICES = [
    ("impresa_1", "1ª impresa"),
    ("impresa_2", "2ª impresa"),
    ("missione", "Missione"),
]
MODULI_FOTO = {k for k, _ in MODULO_FOTO_CHOICES}


def _allegato_upload_to(instance, filename):
    return f"allegati/{instance.diario_id}/{filename}"


class Allegato(models.Model):
    """Foto allegata a un modulo del diario. Vedi docs sez. 4 e 9."""

    diario = models.ForeignKey(Diario, on_delete=models.CASCADE, related_name="allegati")
    modulo = models.CharField(max_length=20, choices=MODULO_FOTO_CHOICES)
    tipo = models.CharField(max_length=10, default="foto")
    file = models.FileField(
        upload_to=_allegato_upload_to,
        blank=True,
        null=True,
        verbose_name="file locale",
        help_text="Rimosso dopo l'upload su Drive",
    )
    drive_file_id = models.CharField(max_length=200, blank=True)
    nome = models.CharField(max_length=255)
    mime = models.CharField(max_length=100, blank=True)
    dimensione = models.PositiveIntegerField(default=0, help_text="bytes")
    caricato_da = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="allegati_caricati"
    )
    stato_sync = models.CharField(
        max_length=10, choices=StatoSync.choices, default=StatoSync.LOCALE
    )
    creato_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["modulo", "creato_at"]
        verbose_name = "allegato"
        verbose_name_plural = "allegati"

    def __str__(self) -> str:
        return f"{self.nome} ({self.modulo})"
