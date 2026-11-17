#!/usr/bin/env bash
# Aggiorna Plancia a una release (tag vX.Y.Z) — modello di quaderno-di-caccia:
# novità dal CHANGELOG.md, controllo delle variabili nuove, manutenzione, backup del database,
# checkout del tag, build delle immagini, avvio e attesa "healthy". Se la versione nuova non
# parte si torna da soli alla precedente; se nel frattempo il database è stato migrato, si resta
# in manutenzione e si indica il backup da ripristinare.
#
# Uso:  scripts/aggiorna.sh                 # l'ultima release (tag vX.Y.Z più alto)
#       scripts/aggiorna.sh v3.1.0          # una release precisa
#       scripts/aggiorna.sh --si v3.1.0     # senza domande (aggiornamento avviato dal web)
#
# --si               non chiede conferme
# --stato-file FILE  scrive l'avanzamento in JSON (contratto in docs/api/aggiornamenti.md)
# --id N             id della richiesta dal web, riportato nel file di stato
# --log FILE         copia anche qui tutto l'output (le ultime righe finiscono nel file di stato)
#
# Il repo resta in "detached HEAD" sul tag installato (deroga al § 3 di INTEGRAZIONE.md del
# frontend, vedi docs/piano-plancia-3.md). Eseguire come proprietario del repo (agesci), mai root.
set -euo pipefail

RADICE="${PLANCIA_RADICE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# git checkout sostituisce questo file mentre bash lo sta leggendo: si esegue da una copia.
if [[ -z "${PLANCIA_RADICE:-}" ]]; then
	copia="$(mktemp)"
	cp "${BASH_SOURCE[0]}" "$copia"
	PLANCIA_RADICE="$RADICE" PLANCIA_COPIA="$copia" exec bash "$copia" "$@"
fi
trap 'rm -f "${PLANCIA_COPIA:-}"' EXIT
cd "$RADICE"
source scripts/_comune.sh
source scripts/_plancia.sh

CONFERMA=true
VERSIONE=""
STATO_FILE=""
ID_RICHIESTA="null"
LOG_FILE=""

uso() { sed -n '2,19p' "$RADICE/scripts/aggiorna.sh" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [[ $# -gt 0 ]]; do
	case "$1" in
		--si) CONFERMA=false; shift ;;
		--stato-file) STATO_FILE="${2:?}"; shift 2 ;;
		--id) ID_RICHIESTA="${2:?}"; shift 2 ;;
		--log) LOG_FILE="${2:?}"; shift 2 ;;
		-h|--help) uso 0 ;;
		-*) avviso "Opzione sconosciuta: $1"; uso 1 ;;
		*) VERSIONE="$1"; shift ;;
	esac
done
[[ "$ID_RICHIESTA" == "null" || "$ID_RICHIESTA" =~ ^[0-9]+$ ]] || errore "--id non valido."
if [[ -n "$LOG_FILE" ]]; then
	mkdir -p "$(dirname "$LOG_FILE")"
	exec > >(tee -a "$LOG_FILE") 2>&1
fi

richiedi_comandi docker git gzip
[[ -f .env ]] || errore ".env mancante: eseguire prima scripts/installa.sh"
docker network inspect "$RETE_PROXY" >/dev/null 2>&1 || errore "Rete $RETE_PROXY mancante."
[[ -z "$STATO_FILE" ]] || richiedi_comandi python3

# --- Stato per la pagina web (scrittura atomica) --------------------------------------------
# stato <fase> <messaggio> [percentuale] [esito]
stato() {
	[[ -n "$STATO_FILE" ]] || return 0
	STATO_ID="$ID_RICHIESTA" STATO_VERSIONE="$VERSIONE" STATO_FASE="$1" STATO_MESSAGGIO="$2" \
	STATO_PERCENTUALE="${3:-}" STATO_ESITO="${4:-}" STATO_LOG="$LOG_FILE" \
	python3 - "$STATO_FILE" <<'PY'
import datetime, json, os, sys, tempfile
destinazione = sys.argv[1]
e = os.environ
righe = []
if e["STATO_LOG"] and os.path.exists(e["STATO_LOG"]):
    with open(e["STATO_LOG"], encoding="utf-8", errors="replace") as f:
        righe = [r.rstrip("\n") for r in f.readlines()[-200:]]
dati = {
    "id": None if e["STATO_ID"] == "null" else int(e["STATO_ID"]),
    "versione": e["STATO_VERSIONE"],
    "fase": e["STATO_FASE"][:40],
    "messaggio": e["STATO_MESSAGGIO"][:500],
    "percentuale": int(e["STATO_PERCENTUALE"]) if e["STATO_PERCENTUALE"] else None,
    "esito": e["STATO_ESITO"] or None,
    "aggiornato_at": datetime.datetime.now().astimezone().isoformat(),
    "log": righe,
}
cartella = os.path.dirname(os.path.abspath(destinazione))
fd, tmp = tempfile.mkstemp(dir=cartella, prefix=".stato-")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(dati, f, ensure_ascii=False)
os.chmod(tmp, 0o664)
os.replace(tmp, destinazione)
PY
}
# Errore fatale prima di aver toccato qualcosa: stato "fallito" ed uscita.
fallisci() {
	stato fine "$1" "" fallito
	errore "$1"
}
chiedi() {
	$CONFERMA || return 0
	local risposta
	read -r -p "$1 [s/N] " risposta
	[[ "$risposta" =~ ^[sS] ]]
}
# La versione $1 è successiva alla $2? (X.Y.Z)
dopo() {
	[[ "$1" != "$2" && "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" == "$1" ]]
}
# Sezioni di CHANGELOG.md (della versione nuova) dopo l'installata, fino alla nuova.
novita() {
	local da="$1" a="$2" elenco="" v registro
	registro="$(git show "$VERSIONE:CHANGELOG.md" 2>/dev/null)" || return 0
	while read -r v; do
		if dopo "$v" "$da" && ! dopo "$v" "$a"; then elenco+=" $v "; fi
	done < <(sed -n 's/^## v\{0,1\}\([0-9][0-9.]*\).*/\1/p' <<<"$registro")
	[[ -n "$elenco" ]] || return 0
	awk -v elenco="$elenco" '
		/^## v?[0-9]/ { v = $2; sub(/^v/, "", v); dentro = index(elenco, " " v " ") > 0 }
		dentro { print }
	' <<<"$registro"
}
# Migrazioni registrate nel database: servono a capire se l'aggiornamento lo ha cambiato.
migrazioni() {
	# shellcheck disable=SC2016  # variabili espanse nel container db
	docker compose exec -T db sh -c \
		'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "select app, name from django_migrations order by 1, 2"'
}

# --- Quale versione ----------------------------------------------------------------------------
stato presa_in_carico "Controllo della versione richiesta" 5
richiedi_albero_pulito
git fetch --tags --force --quiet || fallisci "Non riesco a scaricare le versioni da GitHub (git fetch)."
if [[ -z "$VERSIONE" ]]; then
	VERSIONE="$(git tag -l 'v[0-9]*' --sort=-v:refname | head -1)"
	[[ -n "$VERSIONE" ]] || fallisci "Nessuna release trovata (tag vX.Y.Z)."
fi
[[ "$VERSIONE" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || fallisci "Versione non valida: $VERSIONE (atteso vX.Y.Z)."
git rev-parse -q --verify "refs/tags/$VERSIONE" >/dev/null || fallisci "La release $VERSIONE non esiste."
PRIMA="$(git rev-parse HEAD)"
NOME_PRIMA="$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)"
if [[ "$(git rev-parse "$VERSIONE^{commit}")" == "$PRIMA" ]]; then
	info "Plancia è già alla versione $VERSIONE."
	stato fine "Plancia è già alla versione $VERSIONE." 100 completato
	exit 0
fi
INSTALLATA="$(git describe --tags --abbrev=0 --match 'v[0-9]*' "$PRIMA" 2>/dev/null || true)"
if [[ -n "$INSTALLATA" ]] && ! dopo "${VERSIONE#v}" "${INSTALLATA#v}"; then
	avviso "La $VERSIONE non è successiva alla versione installata ($INSTALLATA)."
	$CONFERMA || fallisci "Dal web si può solo passare a una versione successiva."
	chiedi "Tornare comunque alla $VERSIONE?" || exit 1
fi
info "Aggiornamento da $NOME_PRIMA a $VERSIONE."
NOVITA="$(novita "${INSTALLATA#v}" "${VERSIONE#v}")"
if [[ -n "$NOVITA" ]]; then
	info "Cosa cambia dalla ${INSTALLATA:-versione installata} alla $VERSIONE:"
	echo "$NOVITA"
fi
echo "Note della release: https://github.com/AGESCI-Campania/plancia/releases/tag/$VERSIONE"

# Variabili nuove richieste dalla versione nuova: si controllano prima di toccare qualcosa.
mancanti="$(comm -23 \
	<(git show "$VERSIONE:.env.template" | sed -n 's/^\([A-Z0-9_]*\)=.*/\1/p' | sort -u) \
	<(sed -n 's/^\([A-Z0-9_]*\)=.*/\1/p' .env | sort -u))"
if [[ -n "$mancanti" ]]; then
	avviso "La $VERSIONE richiede variabili nuove in .env (vedi i commenti in .env.template):"
	# shellcheck disable=SC2001
	sed 's/^/      /' <<<"$mancanti" >&2
	fallisci "Aggiungere a .env: $(tr '\n' ' ' <<<"$mancanti")e rilanciare l'aggiornamento."
fi
chiedi "Aggiornare ora a $VERSIONE?" || exit 1

# --- Manutenzione e backup ---------------------------------------------------------------------
stato manutenzione "Attivo la manutenzione" 15
GIA_IN_MANUTENZIONE=false
if [[ "$(manage manutenzione stato 2>/dev/null | tail -n 1)" == "attiva" ]]; then
	GIA_IN_MANUTENZIONE=true
	info "Plancia era già in manutenzione: resterà così alla fine."
else
	manage manutenzione attiva --messaggio "Aggiornamento di Plancia a $VERSIONE in corso." >/dev/null \
		|| avviso "Non riesco ad attivare la manutenzione: proseguo senza."
fi
togli_manutenzione() {
	$GIA_IN_MANUTENZIONE && return 0
	manage manutenzione disattiva >/dev/null \
		|| avviso "Togli la manutenzione da Impostazioni (o: docker compose exec web uv run python manage.py manutenzione disattiva)."
}

stato backup "Backup del database" 25
mkdir -p backups
BACKUP="backups/plancia-db-$(date +%Y%m%d-%H%M%S)-pre-${VERSIONE#v}.sql.gz"
info "Backup del database in $BACKUP"
# shellcheck disable=SC2016  # variabili espanse nel container db
if ! docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$BACKUP" \
	|| [[ ! -s "$BACKUP" ]]; then
	togli_manutenzione
	fallisci "Backup del database non riuscito: aggiornamento annullato."
fi
# Tengo gli ultimi 10 backup di aggiornamento
find backups -maxdepth 1 -name 'plancia-db-*.sql.gz' | sort -r | tail -n +11 | xargs rm -f
MIGRAZIONI_PRIMA="$(migrazioni)"

# --- La versione nuova ---------------------------------------------------------------------------
stato download "Passo al codice della $VERSIONE" 35
git -c advice.detachedHead=false checkout --quiet "$VERSIONE"
stato build "Costruzione delle immagini (qualche minuto)" 45
conserva_immagini
if ! costruisci_immagini --pull; then
	git -c advice.detachedHead=false checkout --quiet "$PRIMA"
	ripristina_immagini || true
	togli_manutenzione
	fallisci "La costruzione della $VERSIONE non è riuscita: resto alla $NOME_PRIMA."
fi
docker compose pull --ignore-buildable --quiet || avviso "Pull delle immagini esterne non riuscito: uso quelle presenti."
stato avvio "Avvio della $VERSIONE (migrazioni del database comprese)" 70
docker compose up -d --remove-orphans || true
stato verifica "Attendo che tutti i servizi rispondano" 85
if servizi_sani 600 "${SERVIZI_SALUTE[@]}"; then
	togli_manutenzione
	docker image prune -f >/dev/null || true
	# Unit systemd: idempotenti, senza sudo stampano il comando per l'amministratore
	installa_servizio_systemd plancia "$UNIT_PROXY"
	installa_backup_systemd
	installa_aggiornamenti_systemd
	info "Fatto: Plancia è alla versione $VERSIONE. Backup del database: $BACKUP"
	stato fine "Plancia è alla versione $VERSIONE." 100 completato
	exit 0
fi

# --- Non risponde: torno alla versione precedente -----------------------------------------------
stato rollback "La $VERSIONE non risponde: torno alla $NOME_PRIMA" 90
avviso "La $VERSIONE non risponde: torno alla $NOME_PRIMA."
docker compose logs --tail 40 web || true
CAMBIATO=false
[[ "$(migrazioni)" != "$MIGRAZIONI_PRIMA" ]] && CAMBIATO=true
git -c advice.detachedHead=false checkout --quiet "$PRIMA"
if $CAMBIATO; then
	# Immagini della versione precedente (coerenti con il codice appena ripristinato), servizi
	# Django fermi (senza riavvii continui) e nginx acceso: la SPA si carica e i percorsi di
	# Django mostrano errore-servizio.html invece del 502 di Caddy. --no-deps perché nginx
	# dipende da web healthy. Al riavvio, dopo il ripristino del backup, parte la precedente.
	ripristina_immagini || costruisci_immagini \
		|| avviso "Non riesco a ripristinare le immagini della $NOME_PRIMA: costruirle con docker compose build web nginx."
	docker compose --profile flower stop web worker beat flower || true
	docker compose up -d --no-deps nginx || true
	messaggio="La $VERSIONE ha già cambiato il database: prima di riavviare la $NOME_PRIMA ripristinare il backup $BACKUP (vedi README.md, «Aggiornamento non riuscito con il database cambiato»). Plancia resta in manutenzione."
	avviso "$messaggio"
	stato fine "$messaggio" "" fallito
	exit 1
fi
# Le immagini della versione precedente sono ancora lì (conserva_immagini): niente build.
if ! ripristina_immagini && ! costruisci_immagini; then
	stato fine "Non riesco a ripristinare la $NOME_PRIMA: Plancia resta in manutenzione. Backup: $BACKUP" "" fallito
	errore "Non riesco a ripristinare la $NOME_PRIMA. Backup: $BACKUP"
fi
docker compose up -d --remove-orphans || true
if servizi_sani 600 "${SERVIZI_SALUTE[@]}"; then
	togli_manutenzione
	stato fine "Aggiornamento non riuscito: Plancia è tornata alla $NOME_PRIMA (database invariato)." "" fallito
	avviso "Plancia è di nuovo alla $NOME_PRIMA e risponde. Il database non era cambiato."
else
	stato fine "Né la $VERSIONE né la $NOME_PRIMA rispondono: Plancia resta in manutenzione. Backup: $BACKUP" "" fallito
	avviso "Neanche la $NOME_PRIMA risponde: Plancia resta in manutenzione. Backup: $BACKUP"
fi
exit 1
