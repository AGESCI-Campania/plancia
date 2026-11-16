# Funzioni specifiche di Plancia condivise da installa.sh e aggiorna.sh — non eseguire direttamente.
# shellcheck shell=bash

# Servizi che devono risultare healthy dopo l'avvio (beat non ha healthcheck)
# shellcheck disable=SC2034  # usata dagli script che includono questo file
SERVIZI_SALUTE=(db redis web worker nginx)

# Esegue un comando Django nel container web in esecuzione
manage() {
	docker compose exec -T web uv run python manage.py "$@"
}

# Installa (o aggiorna) il backup notturno: plancia-backup.service esegue scripts/backup.sh
# come proprietario del repo (es. agesci), plancia-backup.timer lo lancia ogni notte.
# Persistent=true: se il server era spento all'ora prevista, il backup parte all'avvio.
# Idempotente; senza sudo stampa il comando per l'amministratore, come installa_servizio_systemd.
installa_backup_systemd() {
	local dir utente docker_bin cartella="/etc/systemd/system" tmp nome
	if ! command -v systemctl >/dev/null 2>&1 || [[ ! -d /run/systemd/system ]]; then
		avviso "systemd non disponibile: salto l'installazione del backup notturno."
		return 0
	fi
	dir="$(pwd -P)"
	utente="$(stat -c %U "$dir")"
	docker_bin="$(command -v docker)"
	tmp="$(mktemp -d)"
	cat > "$tmp/plancia-backup.service" <<UNIT
# Generato da scripts/installa.sh / aggiorna.sh di ${dir} — non modificare a mano.
[Unit]
Description=AGESCI Campania - backup di Plancia
Wants=docker.service
After=docker.service plancia.service

[Service]
Type=oneshot
User=${utente}
WorkingDirectory=${dir}
Environment=PATH=$(dirname "$docker_bin"):/usr/local/bin:/usr/bin:/bin
ExecStart=${dir}/scripts/backup.sh
UNIT
	cat > "$tmp/plancia-backup.timer" <<UNIT
# Generato da scripts/installa.sh / aggiorna.sh di ${dir} — non modificare a mano.
[Unit]
Description=AGESCI Campania - backup notturno di Plancia

[Timer]
OnCalendar=*-*-* 02:30
RandomizedDelaySec=15min
Persistent=true

[Install]
WantedBy=timers.target
UNIT
	if cmp -s "$tmp/plancia-backup.service" "$cartella/plancia-backup.service" \
		&& cmp -s "$tmp/plancia-backup.timer" "$cartella/plancia-backup.timer" \
		&& systemctl is-enabled --quiet plancia-backup.timer 2>/dev/null; then
		rm -rf "$tmp"
		info "Backup notturno (plancia-backup.timer) già installato e aggiornato."
		return 0
	fi
	if (( EUID != 0 )) && ! sudo -n true 2>/dev/null; then
		rm -rf "$tmp"
		avviso "Il backup notturno (plancia-backup.timer) va installato o aggiornato da un amministratore:"
		avviso "  sudo bash -c 'cd ${dir} && source scripts/_comune.sh && source scripts/_plancia.sh && installa_backup_systemd'"
		return 0
	fi
	info "Installo il backup notturno (plancia-backup.timer)."
	for nome in plancia-backup.service plancia-backup.timer; do
		come_root install -m 644 "$tmp/$nome" "$cartella/$nome"
	done
	rm -rf "$tmp"
	come_root systemctl daemon-reload
	come_root systemctl enable --now --quiet plancia-backup.timer
}

# Elenca le credenziali esterne ancora vuote in .env (passi manuali residui)
credenziali_mancanti() {
	local v
	for v in SOCIAL_SESTANTE_CLIENT_ID SOCIAL_SESTANTE_CLIENT_SECRET ADMIN_EMAILS; do
		[[ -n "$(leggi_var "$v")" ]] || printf '%s\n' "$v"
	done
}
