#!/usr/bin/env bash
#
# Plancia - backup periodico (da invocare via cron)
# Logica ripresa dalla Dashboard Zona: pg_dump + gzip, tar di media/log, retention, notifica.
#
set -euo pipefail
cd "$(dirname "$0")/.."   # radice progetto

# --- Configurazione (sovrascrivibile da ambiente) ---------------------------
BACKUP_DIR="${BACKUP_DIR:-/srv/plancia/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
ENV_FILE="${ENV_FILE:-.env.prod}"
BACKUP_NOTIFY="${BACKUP_NOTIFY:-}"        # email per la notifica (vuoto = nessuna)
TS="$(date +%Y%m%d_%H%M%S)"

# Carica POSTGRES_USER / POSTGRES_DB dall'env di produzione, se presente
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi
PGUSER="${POSTGRES_USER:-plancia}"
PGDB="${POSTGRES_DB:-plancia}"

mkdir -p "$BACKUP_DIR"
echo "$(date '+%F %T') === INIZIO BACKUP Plancia ($TS) ==="

# 1) Dump del database dal container db, compresso
echo "Dump database..."
docker compose --env-file "$ENV_FILE" exec -T db \
    pg_dump -U "$PGUSER" "$PGDB" | gzip > "$BACKUP_DIR/db_${TS}.sql.gz"

# 2) Media + log
echo "Archivio media e log..."
tar -czf "$BACKUP_DIR/media_${TS}.tar.gz" media logs 2>/dev/null || \
    echo "  (media/logs assenti, salto)"

# 3) Copia env
cp "$ENV_FILE" "$BACKUP_DIR/env_${TS}.bak" 2>/dev/null || echo "  (env non trovato)"

# 4) Retention
echo "Pulizia backup oltre ${RETENTION_DAYS} giorni..."
find "$BACKUP_DIR" -name 'db_*.sql.gz'   -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name 'media_*.tar.gz' -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name 'env_*.bak'      -mtime +"$RETENTION_DAYS" -delete

SIZE="$(du -h "$BACKUP_DIR/db_${TS}.sql.gz" | cut -f1)"
echo "Backup DB completato: db_${TS}.sql.gz (${SIZE})"

# 5) Notifica (opzionale)
if [[ -n "$BACKUP_NOTIFY" ]] && command -v mail >/dev/null 2>&1; then
  echo "Backup Plancia OK - $TS (db ${SIZE})" | mail -s "Plancia backup OK" "$BACKUP_NOTIFY"
fi

echo "$(date '+%F %T') === FINE BACKUP Plancia ==="
