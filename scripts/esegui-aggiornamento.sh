#!/usr/bin/env bash
# Esegue l'aggiornamento richiesto dal web (Impostazioni → Aggiornamenti, solo Admin).
# Lanciato da plancia-aggiorna.service quando compare aggiornamenti/richiesta.json; si può
# lanciare anche a mano. Contratto dei file: docs/api/aggiornamenti.md.
#
#   richiesta.json  (Django)  →  in-corso.json (qui)  →  scripts/aggiorna.sh --si
#   stato.json      (aggiorna.sh, e qui in caso di errore prima o dopo)
#
# Uso:  scripts/esegui-aggiornamento.sh
set -euo pipefail

RADICE="${PLANCIA_RADICE_RUNNER:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# aggiorna.sh fa il checkout del tag e può sostituire anche questo file: si esegue da una copia.
if [[ -z "${PLANCIA_RADICE_RUNNER:-}" ]]; then
	copia="$(mktemp)"
	cp "${BASH_SOURCE[0]}" "$copia"
	PLANCIA_RADICE_RUNNER="$RADICE" PLANCIA_COPIA_RUNNER="$copia" exec bash "$copia" "$@"
fi
trap 'rm -f "${PLANCIA_COPIA_RUNNER:-}"' EXIT
cd "$RADICE"
source scripts/_comune.sh

CARTELLA="aggiornamenti"
RICHIESTA="$CARTELLA/richiesta.json"
IN_CORSO="$CARTELLA/in-corso.json"
STATO="$CARTELLA/stato.json"
richiedi_comandi python3 flock

mkdir -p "$CARTELLA/log"
# Una sola esecuzione alla volta
exec 9>"$CARTELLA/.lock"
flock -n 9 || { info "Un aggiornamento è già in corso."; exit 0; }

[[ -f "$RICHIESTA" ]] || { info "Nessuna richiesta di aggiornamento."; exit 0; }
[[ ! -e "$IN_CORSO" ]] || errore "C'è già $IN_CORSO: un aggiornamento precedente si è interrotto? Controllare e rimuoverlo."
mv "$RICHIESTA" "$IN_CORSO"

# Campi della richiesta, validati: id intero, versione vX.Y.Z (il tag lo verifica aggiorna.sh)
read -r ID VERSIONE < <(python3 - "$IN_CORSO" <<'PY'
import json, re, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        r = json.load(f)
    i, v = int(r["id"]), str(r["versione"])
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", v):
        raise ValueError(v)
    print(i, v)
except Exception:
    print("0 non-valida")
PY
)

# Stato finale scritto qui (richiesta rifiutata o aggiorna.sh uscito senza esito)
stato_finale() {
	python3 - "$STATO" "$ID" "$VERSIONE" "$1" "$2" <<'PY'
import datetime, json, os, sys, tempfile
dest, i, v, esito, messaggio = sys.argv[1:6]
dati = {"id": int(i) or None, "versione": v, "fase": "fine", "messaggio": messaggio,
        "percentuale": None, "esito": esito,
        "aggiornato_at": datetime.datetime.now().astimezone().isoformat(), "log": []}
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(dest)), prefix=".stato-")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(dati, f, ensure_ascii=False)
os.chmod(tmp, 0o664)
os.replace(tmp, dest)
PY
}

if [[ "$ID" == "0" ]]; then
	stato_finale fallito "Richiesta di aggiornamento non valida: ignorata."
	rm -f "$IN_CORSO"
	errore "Richiesta non valida in $IN_CORSO."
fi

LOG="$CARTELLA/log/aggiornamento-${ID}-$(date +%Y%m%d-%H%M%S).log"
info "Aggiornamento richiesto dal web: $VERSIONE (richiesta $ID), log in $LOG"
esito=0
scripts/aggiorna.sh --si --stato-file "$STATO" --id "$ID" --log "$LOG" "$VERSIONE" || esito=$?

# aggiorna.sh scrive sempre lo stato finale; se è uscito prima (errore imprevisto) lo si chiude qui.
chiuso="$(python3 - "$STATO" "$ID" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        s = json.load(f)
    print("si" if s.get("id") == int(sys.argv[2]) and s.get("esito") else "no")
except Exception:
    print("no")
PY
)"
if [[ "$chiuso" != "si" ]]; then
	stato_finale fallito "Aggiornamento interrotto per un errore imprevisto (codice $esito): vedere $LOG sul server."
fi
rm -f "$IN_CORSO"
# Log degli aggiornamenti: gli ultimi 20
find "$CARTELLA/log" -name 'aggiornamento-*.log' | sort -r | tail -n +21 | xargs rm -f
exit "$esito"
