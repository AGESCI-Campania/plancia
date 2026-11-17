# Funzioni specifiche di Plancia condivise da installa.sh e aggiorna.sh — non eseguire direttamente.
# shellcheck shell=bash

# Servizi che devono risultare healthy dopo l'avvio (beat non ha healthcheck)
# shellcheck disable=SC2034  # usata dagli script che includono questo file
SERVIZI_SALUTE=(db redis web worker nginx)

# uid/gid dell'utente che lancia gli script (il proprietario del repo, agesci): l'immagine
# crea l'utente del container con gli stessi, vedi Dockerfile e build.args nel compose.
APP_UID="$(id -u)"
APP_GID="$(id -g)"
export APP_UID APP_GID

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

# Costruisce le immagini una alla volta (Django, poi nginx con la SPA): in parallelo il picco
# di memoria (collectstatic + build di Vite) può far terminare la build per memoria esaurita.
costruisci_immagini() {
	local servizio
	for servizio in web nginx; do
		docker compose build "$@" "$servizio" || return 1
	done
}

# Immagini costruite in locale (docker-compose.yml): prima di costruire la versione nuova si
# tengono quelle in uso con il tag "precedente", così il ritorno indietro non deve ricostruire.
IMMAGINI_LOCALI=(plancia plancia-nginx)
conserva_immagini() {
	local img
	for img in "${IMMAGINI_LOCALI[@]}"; do
		if docker image inspect "$img:locale" >/dev/null 2>&1; then
			docker image tag "$img:locale" "$img:precedente"
		fi
	done
}
ripristina_immagini() {
	local img
	for img in "${IMMAGINI_LOCALI[@]}"; do
		docker image inspect "$img:precedente" >/dev/null 2>&1 || return 1
	done
	for img in "${IMMAGINI_LOCALI[@]}"; do
		docker image tag "$img:precedente" "$img:locale"
	done
}

# Come attendi_salute di _comune.sh, ma restituisce 1 invece di uscire (serve al rollback)
servizi_sani() {
	local timeout="$1"; shift
	local fine=$((SECONDS + timeout)) servizio id stato tutti_ok
	info "Attendo che i servizi siano healthy: $*"
	while (( SECONDS < fine )); do
		tutti_ok=1
		for servizio in "$@"; do
			id="$(docker compose ps -q "$servizio")"
			stato="$( [[ -n "$id" ]] && docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" || echo assente)"
			if [[ "$stato" == "unhealthy" ]]; then
				# Docker lo dichiara solo dopo start_period e i tentativi del healthcheck: inutile aspettare
				avviso "Il servizio $servizio è unhealthy."
				docker compose ps >&2
				return 1
			fi
			[[ "$stato" == "healthy" ]] || tutti_ok=0
		done
		(( tutti_ok )) && { info "Tutti i servizi sono healthy."; return 0; }
		sleep 5
	done
	docker compose ps >&2
	return 1
}

# Installa (o aggiorna) l'esecuzione degli aggiornamenti richiesti dal web (solo Admin, pagina
# Impostazioni → Aggiornamenti): Django scrive aggiornamenti/richiesta.json (bind mount),
# plancia-aggiorna.path lo vede e avvia plancia-aggiorna.service, che lancia
# scripts/esegui-aggiornamento.sh come proprietario del repo. Il container non ha mai accesso a
# Docker. Idempotente; senza sudo stampa il comando per l'amministratore.
installa_aggiornamenti_systemd() {
	local dir utente docker_bin cartella="/etc/systemd/system" tmp nome
	if ! command -v systemctl >/dev/null 2>&1 || [[ ! -d /run/systemd/system ]]; then
		avviso "systemd non disponibile: salto l'aggiornamento dal web."
		return 0
	fi
	dir="$(pwd -P)"
	utente="$(stat -c %U "$dir")"
	docker_bin="$(command -v docker)"
	tmp="$(mktemp -d)"
	cat > "$tmp/plancia-aggiorna.service" <<UNIT
# Generato da scripts/installa.sh / aggiorna.sh di ${dir} — non modificare a mano.
[Unit]
Description=AGESCI Campania - aggiornamento di Plancia richiesto dal web
Wants=docker.service
After=docker.service plancia.service

[Service]
Type=oneshot
User=${utente}
WorkingDirectory=${dir}
Environment=PATH=$(dirname "$docker_bin"):/usr/local/bin:/usr/bin:/bin
ExecStart=${dir}/scripts/esegui-aggiornamento.sh
TimeoutStartSec=45min
UNIT
	cat > "$tmp/plancia-aggiorna.path" <<UNIT
# Generato da scripts/installa.sh / aggiorna.sh di ${dir} — non modificare a mano.
[Unit]
Description=AGESCI Campania - richieste di aggiornamento di Plancia dal web

[Path]
PathExists=${dir}/aggiornamenti/richiesta.json
Unit=plancia-aggiorna.service

[Install]
WantedBy=paths.target
UNIT
	if cmp -s "$tmp/plancia-aggiorna.service" "$cartella/plancia-aggiorna.service" \
		&& cmp -s "$tmp/plancia-aggiorna.path" "$cartella/plancia-aggiorna.path" \
		&& systemctl is-enabled --quiet plancia-aggiorna.path 2>/dev/null; then
		rm -rf "$tmp"
		info "Aggiornamento dal web (plancia-aggiorna.path) già installato e aggiornato."
		return 0
	fi
	if (( EUID != 0 )) && ! sudo -n true 2>/dev/null; then
		rm -rf "$tmp"
		avviso "L'aggiornamento dal web (plancia-aggiorna.path) va installato o aggiornato da un amministratore:"
		avviso "  sudo bash -c 'cd ${dir} && source scripts/_comune.sh && source scripts/_plancia.sh && installa_aggiornamenti_systemd'"
		return 0
	fi
	info "Installo l'aggiornamento dal web (plancia-aggiorna.path)."
	for nome in plancia-aggiorna.service plancia-aggiorna.path; do
		come_root install -m 644 "$tmp/$nome" "$cartella/$nome"
	done
	rm -rf "$tmp"
	come_root systemctl daemon-reload
	come_root systemctl enable --now --quiet plancia-aggiorna.path
}

# Elenca le credenziali esterne ancora vuote in .env (passi manuali residui)
credenziali_mancanti() {
	local v
	for v in SOCIAL_SESTANTE_CLIENT_ID SOCIAL_SESTANTE_CLIENT_SECRET ADMIN_EMAILS; do
		[[ -n "$(leggi_var "$v")" ]] || printf '%s\n' "$v"
	done
}
