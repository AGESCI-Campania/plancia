# Plancia — systemd unit generato da deploy/configure-prod.sh
# Installazione:
#   sudo cp deploy/plancia.service /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now plancia
#
# Comandi utili:
#   sudo systemctl status plancia
#   sudo systemctl restart plancia
#   sudo journalctl -u plancia -f

[Unit]
Description=Plancia — Guidoncini Verdi (AGESCI Campania)
Documentation=https://github.com/AGESCI-Campania/plancia
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
Environment=COMPOSE_PROFILES=${COMPOSE_PROFILES}
ExecStartPre=/usr/bin/docker compose --env-file .env.prod pull --quiet
ExecStart=/usr/bin/docker compose --env-file .env.prod up -d --wait
ExecStop=/usr/bin/docker compose --env-file .env.prod down
ExecReload=/usr/bin/docker compose --env-file .env.prod restart web worker beat
TimeoutStartSec=300
TimeoutStopSec=120
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
