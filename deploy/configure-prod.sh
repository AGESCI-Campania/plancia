#!/usr/bin/env bash
#
# Plancia - configurazione di produzione
# Genera .env.prod, sceglie la modalita' di proxying e la porta, rende il vhost
# e genera il file systemd plancia.service per l'avvio automatico.
# Idempotente e ri-eseguibile. Richiede: bash, docker compose, python3.
#
set -euo pipefail
cd "$(dirname "$0")/.."

# ----------------------------------------------------------------------------
# Default e parametri (flag opzionali; altrimenti prompt)
# ----------------------------------------------------------------------------
SERVER_NAME="${SERVER_NAME:-}"
PROXY_MODE="${PROXY_MODE:-}"        # nginx-docker | nginx-host | apache-host
APP_PORT="${APP_PORT:-8000}"
TLS_MODE="${TLS_MODE:-external}"    # letsencrypt | self-signed | external
INSTALL_DIR="${INSTALL_DIR:-$(pwd)}"
RUN_COMPOSE="${RUN_COMPOSE:-ask}"   # yes | no | ask

usage() {
  cat <<USAGE
Uso: deploy/configure-prod.sh [opzioni]
  --server-name NOME     dominio (es. plancia.agescicampania.org)
  --proxy MODE           nginx-docker | nginx-host | apache-host
  --port N               porta applicativa (default 8000)
  --tls MODE             letsencrypt | self-signed | external (default external)
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
    --tls)          TLS_MODE="$2"; shift 2;;
    --install-dir)  INSTALL_DIR="$2"; shift 2;;
    --run)          RUN_COMPOSE="yes"; shift;;
    --no-run)       RUN_COMPOSE="no"; shift;;
    -h|--help)      usage; exit 0;;
    *) echo "Opzione sconosciuta: $1"; usage; exit 1;;
  esac
done

ask() { local p="$1" d="${2:-}" a; read -rp "$p${d:+ [$d]}: " a; echo "${a:-$d}"; }

[[ -z "$SERVER_NAME" ]] && SERVER_NAME="$(ask 'Dominio (server_name)' 'plancia.agescicampania.org')"
if [[ -z "$PROXY_MODE" ]]; then
  echo "Modalita' di proxying:"
  echo "  1) nginx-docker  (nginx nel compose, pubblica 80/443)"
  echo "  2) nginx-host    (nginx gia' installato sull'host)"
  echo "  3) apache-host   (Apache 2 gia' installato sull'host)"
  case "$(ask 'Scelta' '1')" in
    1) PROXY_MODE="nginx-docker";;
    2) PROXY_MODE="nginx-host";;
    3) PROXY_MODE="apache-host";;
    *) echo "Scelta non valida"; exit 1;;
  esac
fi
APP_PORT="$(ask 'Porta applicativa' "$APP_PORT")"

# ----------------------------------------------------------------------------
# .env.prod  (crea i secret mancanti, preserva quelli esistenti)
# ----------------------------------------------------------------------------
gen() { python3 -c 'import secrets;print(secrets.token_urlsafe(48))'; }
if [[ ! -f .env.prod ]]; then
  echo "Genero .env.prod da .env.example ..."
  cp .env.example .env.prod
  sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(gen)|" .env.prod
  DBPASS="$(gen)"
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DBPASS}|" .env.prod
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgres://plancia:${DBPASS}@db:5432/plancia|" .env.prod
fi
# Allinea i valori scelti
sed -i "s|^APP_PORT=.*|APP_PORT=${APP_PORT}|" .env.prod
sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=${SERVER_NAME}|" .env.prod
sed -i "s|^CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=https://${SERVER_NAME}|" .env.prod
echo "OK: .env.prod aggiornato (completa SMTP e OAuth a mano)."

# ----------------------------------------------------------------------------
# Profilo compose secondo la modalita'
# ----------------------------------------------------------------------------
case "$PROXY_MODE" in
  nginx-docker)         COMPOSE_PROFILES="proxy-nginx";;
  nginx-host|apache-host) COMPOSE_PROFILES="";;
  *) echo "PROXY_MODE non valido: $PROXY_MODE"; exit 1;;
esac

# Comando compose da usare nei messaggi e negli alias
if [[ -n "$COMPOSE_PROFILES" ]]; then
  COMPOSE_CMD="COMPOSE_PROFILES=${COMPOSE_PROFILES} docker compose --env-file .env.prod"
else
  COMPOSE_CMD="docker compose --env-file .env.prod"
fi

# ----------------------------------------------------------------------------
# Rende il vhost per le modalita' host
# ----------------------------------------------------------------------------
render_tpl() { sed -e "s|\${SERVER_NAME}|${SERVER_NAME}|g" -e "s|\${APP_PORT}|${APP_PORT}|g" "$1"; }
case "$PROXY_MODE" in
  nginx-host)
    OUT="deploy/plancia.nginx.conf"; render_tpl deploy/nginx.vhost.tpl > "$OUT"
    echo "vhost nginx generato: $OUT"
    echo "  -> copialo in /etc/nginx/sites-available/, abilitalo e: nginx -t && systemctl reload nginx";;
  apache-host)
    OUT="deploy/plancia.apache.conf"; render_tpl deploy/apache.vhost.tpl > "$OUT"
    echo "vhost Apache generato: $OUT"
    echo "  -> copialo in /etc/apache2/sites-available/, a2ensite e: systemctl reload apache2";;
  nginx-docker)
    echo "Proxy nginx dockerizzato: metti i certificati in deploy/certs/{fullchain,privkey}.pem";;
esac

# ----------------------------------------------------------------------------
# Crea la directory logs/ sull'host (il volume Docker la creerebbe come root)
# ----------------------------------------------------------------------------
mkdir -p logs/email
echo "OK: directory logs/ pronta."

# ----------------------------------------------------------------------------
# Genera il file systemd unit
# ----------------------------------------------------------------------------
SERVICE_OUT="deploy/plancia.service"
sed \
  -e "s|\${INSTALL_DIR}|${INSTALL_DIR}|g" \
  -e "s|\${COMPOSE_PROFILES}|${COMPOSE_PROFILES}|g" \
  deploy/plancia.service.tpl > "$SERVICE_OUT"
echo ""
echo "File systemd generato: $SERVICE_OUT"
echo "  Per abilitare l'avvio automatico:"
echo "    sudo cp ${SERVICE_OUT} /etc/systemd/system/plancia.service"
echo "    sudo systemctl daemon-reload"
echo "    sudo systemctl enable --now plancia"
echo ""
echo "  Comandi utili:"
echo "    sudo systemctl status plancia"
echo "    sudo systemctl restart plancia"
echo "    sudo journalctl -u plancia -f"
echo ""
echo "  Log applicativi (persistono sull'host in logs/):"
echo "    tail -f ${INSTALL_DIR}/logs/plancia.log     # log Django (errori 500, warning, info)"
echo "    docker compose logs -f web                  # stdout container web (gunicorn)"
echo "    docker compose logs -f worker               # stdout worker Celery"

# ----------------------------------------------------------------------------
# Avvio (opzionale)
# ----------------------------------------------------------------------------
if [[ "$RUN_COMPOSE" == "ask" ]]; then
  RUN_COMPOSE="$(ask 'Avvio docker compose ora? (yes/no)' 'no')"
fi
if [[ "$RUN_COMPOSE" == "yes" ]]; then
  export COMPOSE_PROFILES
  docker compose --env-file .env.prod build
  docker compose --env-file .env.prod up -d
  docker compose --env-file .env.prod exec -T web uv run python manage.py migrate --noinput
  docker compose --env-file .env.prod exec -T web uv run python manage.py collectstatic --noinput
  echo "Plancia avviata. Porta interna app: ${APP_PORT}, modalita': ${PROXY_MODE}."
else
  echo "Configurazione completata. Per avviare manualmente:"
  echo "  ${COMPOSE_CMD} up -d"
fi
