#!/usr/bin/env bash
# Aggiorna Plancia a una nuova release: scarica l'ultima versione da git, ricostruisce
# l'immagine, fa il backup del database e riavvia lo stack (le migrazioni le applica
# l'entrypoint del container web).
#
# Uso:  scripts/aggiorna.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_comune.sh

richiedi_comandi docker git gzip
[[ -f .env ]] || errore ".env mancante: eseguire prima scripts/installa.sh"
docker network inspect "$RETE_PROXY" >/dev/null 2>&1 || errore "Rete $RETE_PROXY mancante."

# git pull può modificare questo stesso script: dopo il pull si riparte con la versione nuova
if [[ "${1:-}" != "--dopo-pull" ]]; then
	richiedi_albero_pulito
	info "Scarico gli aggiornamenti da git."
	git pull --ff-only
	exec "$0" --dopo-pull
fi
source scripts/_plancia.sh

controlla_var_nuove

versione="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -n 1)"
info "Aggiorno Plancia alla versione $versione ($(git log -1 --format=%h))."

# --- Immagini (prima di fermare qualcosa: se la build fallisce lo stack resta com'è) ---
docker compose build --pull
docker compose pull --ignore-buildable

# --- Backup del database prima delle migrazioni ---
docker compose up -d db
attendi_salute 120 db
mkdir -p backups
backup="backups/plancia-db-$(date +%Y%m%d-%H%M%S)-pre-$versione.sql.gz"
info "Backup del database in $backup"
# shellcheck disable=SC2016  # variabili espanse nel container db
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$backup"
[[ -s "$backup" ]] || errore "Backup vuoto: aggiornamento interrotto."
# Tengo gli ultimi 10 backup di aggiornamento
find backups -maxdepth 1 -name 'plancia-db-*.sql.gz' | sort -r | tail -n +11 | xargs rm -f

# --- Riavvio con le nuove immagini ---
docker compose up -d --remove-orphans
attendi_salute 600 "${SERVIZI_SALUTE[@]}"
docker image prune -f >/dev/null

# Idempotente: installa la unit se manca, la aggiorna se è cambiata
installa_servizio_systemd plancia "$UNIT_PROXY"
installa_backup_systemd

mancanti="$(credenziali_mancanti | tr '\n' ' ')"
if [[ -n "$mancanti" ]]; then
	avviso "Variabili ancora vuote in .env: $mancanti"
fi
cat <<EOF

Aggiornamento completato (Plancia $versione). Backup del database: $backup
Se qualcosa non va: docker compose logs --tail 100 web worker
Ripristino (solo in emergenza): git checkout della release precedente, poi
  docker compose stop web worker beat
  docker compose exec -T db sh -c 'dropdb -U "\$POSTGRES_USER" "\$POSTGRES_DB" && createdb -U "\$POSTGRES_USER" "\$POSTGRES_DB"'
  gunzip -c $backup | docker compose exec -T db sh -c 'psql -U "\$POSTGRES_USER" "\$POSTGRES_DB"'
  docker compose up -d --build
EOF
