#!/usr/bin/env bash
# Backup completo di Plancia in un unico archivio: dump del database, .env (contiene
# DJANGO_SECRET_KEY e le credenziali OAuth) e media (allegati in attesa di Drive).
# Eseguito ogni notte dal timer systemd plancia-backup.timer; si può lanciare anche a mano.
#
# Ripristino. Su un server nuovo copiare prima env dell'archivio in .env (chmod 600) e poi
# lanciare scripts/installa.sh: così il database nasce con la stessa POSTGRES_PASSWORD.
#   mkdir /tmp/ripristino && tar -xzf <archivio> -C /tmp/ripristino
#   docker compose stop web worker beat
#   docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
#   docker compose exec -T db sh -c 'psql -q -U "$POSTGRES_USER" "$POSTGRES_DB"' < /tmp/ripristino/database.sql
#   docker compose up -d --wait web
#   docker compose exec -T web tar -C /app -xf - < /tmp/ripristino/media.tar
#   docker compose up -d && rm -rf /tmp/ripristino
#
# Uso:  scripts/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_comune.sh

richiedi_comandi docker tar gzip
[[ -f .env ]] || errore ".env mancante: Plancia non è installata in $(pwd -P)."

dest="$(leggi_var BACKUP_DIR)"; dest="${dest:-backups}"
giorni="$(leggi_var BACKUP_GIORNI)"; giorni="${giorni:-14}"
[[ "$giorni" =~ ^[0-9]+$ ]] || errore "BACKUP_GIORNI non valido: $giorni"

# Archivi leggibili dal gruppo della cartella (es. l'utente del NAS che li scarica), non da altri
umask 027
mkdir -p "$dest"

versione="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -n 1)"
nome="plancia-$(date +%Y%m%d-%H%M%S)-${versione}.tar.gz"
lavoro="$(mktemp -d)"
trap 'rm -rf "$lavoro"' EXIT

info "Dump del database."
# shellcheck disable=SC2016  # variabili espanse nel container db
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$lavoro/database.sql"
[[ -s "$lavoro/database.sql" ]] || errore "Dump del database vuoto."
cp .env "$lavoro/env"

info "Archivio i media."
docker compose exec -T web tar -C /app -cf - media > "$lavoro/media.tar"

info "Creo l'archivio $dest/$nome"
# Scritto con un nome nascosto e rinominato alla fine: chi sincronizza la cartella non vede
# mai un archivio a metà (escludere i file che iniziano con "." dalla sincronizzazione)
tar -czf "$dest/.$nome.parziale" -C "$lavoro" database.sql env media.tar
mv "$dest/.$nome.parziale" "$dest/$nome"

# Rotazione: solo gli archivi di questo script, non quelli di aggiorna.sh
find "$dest" -maxdepth 1 -name 'plancia-2*.tar.gz' -mtime "+$giorni" -delete
find "$dest" -maxdepth 1 -name '.plancia-*.parziale' -mmin +120 -delete

info "Backup completato: $dest/$nome ($(du -h "$dest/$nome" | cut -f1))."
