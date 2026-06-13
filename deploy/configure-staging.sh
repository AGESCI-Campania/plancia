#!/usr/bin/env bash
#
# Plancia Staging - configurazione dell'ambiente di staging
# Genera .env.staging, genera il vhost e prepara la directory.
# Idempotente e ri-eseguibile.
# Richiede: bash, docker compose, python3.
#
set -euo pipefail
cd "$(dirname "$0")/.."

SERVER_NAME="${SERVER_NAME:-staging.plancia.agescicampania.org}"
PROXY_MODE="${PROXY_MODE:-}"       # nginx-host | apache-host
APP_PORT="${APP_PORT:-8002}"
INSTALL_DIR="${INSTALL_DIR:-$(pwd)}"
RUN_COMPOSE="${RUN_COMPOSE:-ask}"

usage() {
  cat <<USAGE
Uso: deploy/configure-staging.sh [opzioni]
  --server-name NOME     dominio staging (default: staging.plancia.agescicampania.org)
  --proxy MODE           nginx-host | apache-host
  --port N               porta applicativa (default 8002)
  --install-dir DIR      directory di installazione (default: directory corrente)
  --run / --no-run       avvia (o no) docker compose al termine
  -h, --help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --server-name)  SERVER_NAME="$2"; shift 2;;
    --proxy)        PROXY_MODE="$2"; shift 2;;
    --port)         APP_PORT="$2"; shift 2;;
    --install-dir)  INSTALL_DIR="$2"; shift 2;;
    --run)          RUN_COMPOSE="yes"; shift;;
    --no-run)       RUN_COMPOSE="no"; shift;;
    -h|--help)      usage; exit 0;;
    *) echo "Opzione sconosciuta: $1"; usage; exit 1;;
  esac
done

ask() { local p="$1" d="${2:-}" a; read -rp "$p${d:+ [$d]}: " a; echo "${a:-$d}"; }

if [[ -z "$PROXY_MODE" ]]; then
  echo "Modalità di proxying:"
  echo "  1) nginx-host    (nginx già installato sull'host)"
  echo "  2) apache-host   (Apache 2 già installato sull'host)"
  case "$(ask 'Scelta' '1')" in
    1) PROXY_MODE="nginx-host";;
    2) PROXY_MODE="apache-host";;
    *) echo "Scelta non valida"; exit 1;;
  esac
fi

# ----------------------------------------------------------------------------
# .env.staging  (crea i secret mancanti, preserva quelli esistenti)
# ----------------------------------------------------------------------------
gen() { python3 -c 'import secrets;print(secrets.token_urlsafe(48))'; }
if [[ ! -f .env.staging ]]; then
  echo "Genero .env.staging da .env.staging.example ..."
  cp .env.staging.example .env.staging
  sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(gen)|" .env.staging
  DBPASS="$(gen)"
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DBPASS}|" .env.staging
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgres://plancia_staging:${DBPASS}@db:5432/plancia_staging|" .env.staging
fi
# Allinea i valori scelti
sed -i "s|^APP_PORT=.*|APP_PORT=${APP_PORT}|" .env.staging
sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=${SERVER_NAME},127.0.0.1|" .env.staging
sed -i "s|^CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=https://${SERVER_NAME}|" .env.staging
sed -i "s|^BASE_URL=.*|BASE_URL=https://${SERVER_NAME}|" .env.staging
sed -i "s|${SERVER_NAME}/drive/oauth/callback/|${SERVER_NAME}/drive/oauth/callback/|" .env.staging
echo "OK: .env.staging aggiornato."

# ----------------------------------------------------------------------------
# Vhost
# ----------------------------------------------------------------------------
render_tpl() {
  sed \
    -e "s|\${SERVER_NAME}|${SERVER_NAME}|g" \
    -e "s|\${APP_PORT}|${APP_PORT}|g" \
    -e "s|\${INSTALL_DIR}|${INSTALL_DIR}|g" \
    "$1"
}
case "$PROXY_MODE" in
  nginx-host)
    OUT="deploy/plancia-staging.nginx.conf"
    render_tpl deploy/nginx.vhost.tpl > "$OUT"
    echo "vhost nginx generato: $OUT"
    echo "  -> sudo cp $OUT /etc/nginx/sites-available/plancia-staging.conf"
    echo "     sudo ln -sf /etc/nginx/sites-available/plancia-staging.conf /etc/nginx/sites-enabled/"
    echo "     sudo certbot --nginx -d ${SERVER_NAME}"
    echo "     sudo nginx -t && sudo systemctl reload nginx";;
  apache-host)
    OUT="deploy/plancia-staging.apache.conf"
    render_tpl deploy/apache.vhost.tpl > "$OUT"
    echo "vhost Apache generato: $OUT"
    echo "  -> sudo cp $OUT /etc/apache2/sites-available/plancia-staging.conf"
    echo "     sudo a2ensite plancia-staging.conf"
    echo "     sudo certbot --apache -d ${SERVER_NAME}"
    echo "     sudo systemctl reload apache2";;
esac

# ----------------------------------------------------------------------------
# Directory di log
# ----------------------------------------------------------------------------
mkdir -p logs-staging/email staticfiles-staging
echo "OK: directory logs-staging/ e staticfiles-staging/ pronte."

# ----------------------------------------------------------------------------
# Systemd unit per lo staging
# ----------------------------------------------------------------------------
SERVICE_OUT="deploy/plancia-staging.service"
cat > "$SERVICE_OUT" <<UNIT
# Plancia Staging — systemd unit
[Unit]
Description=Plancia Staging — Guidoncini Verdi v2 (AGESCI Campania)
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --wait
ExecStop=/usr/bin/docker compose -f docker-compose.staging.yml --env-file .env.staging down
ExecReload=/bin/sh -c 'cd ${INSTALL_DIR} && /usr/bin/docker compose -f docker-compose.staging.yml --env-file .env.staging build --no-cache web worker beat && /usr/bin/docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --wait web worker beat'
TimeoutStartSec=300
TimeoutStopSec=120
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
echo "Systemd unit generato: $SERVICE_OUT"
echo "  -> sudo cp $SERVICE_OUT /etc/systemd/system/plancia-staging.service"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable --now plancia-staging"

# ----------------------------------------------------------------------------
# Avvio
# ----------------------------------------------------------------------------
COMPOSE_CMD="docker compose -f docker-compose.staging.yml --env-file .env.staging"

if [[ "$RUN_COMPOSE" == "ask" ]]; then
  RUN_COMPOSE="$(ask 'Avvio docker compose staging ora? (yes/no)' 'no')"
fi
if [[ "$RUN_COMPOSE" == "yes" ]]; then
  $COMPOSE_CMD build --no-cache web worker beat
  $COMPOSE_CMD run --rm web uv run python manage.py collectstatic --noinput
  $COMPOSE_CMD up -d
  echo "Staging avviato su porta ${APP_PORT} → https://${SERVER_NAME}"
else
  echo ""
  echo "Per avviare manualmente:"
  echo "  $COMPOSE_CMD build --no-cache web worker beat"
  echo "  $COMPOSE_CMD run --rm web uv run python manage.py collectstatic --noinput"
  echo "  $COMPOSE_CMD up -d"
fi
