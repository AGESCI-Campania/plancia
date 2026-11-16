# Funzioni condivise da installa.sh e aggiorna.sh — non eseguire direttamente.
# shellcheck shell=bash

# shellcheck disable=SC2034  # usate dagli script che includono questo file
RETE_PROXY="agesci-proxy"
# shellcheck disable=SC2034
UNIT_PROXY="agesci-campania-web-frontend.service"   # unit systemd del reverse proxy

info()   { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
avviso() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
errore() { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

richiedi_comandi() {
	local cmd
	for cmd in "$@"; do
		command -v "$cmd" >/dev/null 2>&1 || errore "Comando richiesto non trovato: $cmd"
	done
	docker compose version >/dev/null 2>&1 || errore "Serve Docker Compose v2 (docker compose)"
}

# Valore di una variabile in .env (vuoto se assente)
leggi_var() {
	sed -n "s/^$1=//p" .env | tail -n 1
}

# Imposta (o aggiunge) KEY=VALUE in .env senza sed -i, portabile e sicuro con / e + nei valori
imposta_var() {
	local chiave="$1" valore="$2" tmp
	tmp="$(mktemp)"
	awk -v k="$chiave" -v v="$valore" '
		BEGIN { trovata = 0 }
		index($0, k "=") == 1 { print k "=" v; trovata = 1; next }
		{ print }
		END { if (!trovata) print k "=" v }
	' .env > "$tmp"
	cat "$tmp" > .env
	rm -f "$tmp"
}

# Segnala le variabili presenti in .env.template ma mancanti in .env
controlla_var_nuove() {
	local mancanti
	mancanti="$(comm -23 \
		<(sed -n 's/^\([A-Z0-9_]*\)=.*/\1/p' .env.template | sort -u) \
		<(sed -n 's/^\([A-Z0-9_]*\)=.*/\1/p' .env | sort -u))"
	if [[ -n "$mancanti" ]]; then
		avviso "Variabili nuove in .env.template non presenti in .env:"
		# shellcheck disable=SC2001  # indentazione di ogni riga, non una sostituzione semplice
		sed 's/^/      /' <<< "$mancanti" >&2
		avviso "Aggiungerle a .env (vedi i commenti in .env.template) e rilanciare."
		return 1
	fi
}

richiedi_albero_pulito() {
	if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
		errore "Ci sono modifiche locali non committate: il server deve rispecchiare git. Annullarle o committarle prima."
	fi
}

# Esegue un comando come root (direttamente se lo siamo già, altrimenti con sudo)
come_root() {
	if (( EUID == 0 )); then
		"$@"
	else
		command -v sudo >/dev/null 2>&1 || errore "Servono i permessi di root (sudo non disponibile): $*"
		sudo "$@"
	fi
}

# Installa (o aggiorna) e abilita la unit systemd che avvia lo stack compose della directory
# corrente al boot, nell'ordine giusto rispetto alle unit da cui dipende. Idempotente.
#
# Uso:  installa_servizio_systemd <nome-unit> [unit-da-cui-dipende.service ...]
#       es. installa_servizio_systemd plancia "$UNIT_PROXY"
#
# La unit è oneshot: lancia `docker compose up -d --wait` e termina quando i servizi sono
# healthy, così le unit che la seguono (After=) partono solo a servizi pronti. Non ha
# ExecStop: allo spegnimento ci pensa Docker, e la restart policy `unless-stopped` dei
# container resta il meccanismo che li riavvia dopo un crash o un riavvio del demone Docker.
installa_servizio_systemd() {
	local nome="$1"; shift
	local file="/etc/systemd/system/${nome}.service" dipendenze="" dir docker_bin tmp
	if ! command -v systemctl >/dev/null 2>&1 || [[ ! -d /run/systemd/system ]]; then
		avviso "systemd non disponibile: salto l'installazione della unit ${nome}.service."
		return 0
	fi
	(( $# )) && dipendenze=" $*"
	dir="$(pwd -P)"
	docker_bin="$(command -v docker)"
	tmp="$(mktemp)"
	cat > "$tmp" <<EOF
# Generato da scripts/installa.sh / aggiorna.sh di ${dir} — non modificare a mano.
[Unit]
Description=AGESCI Campania - ${nome} (Docker Compose)
Wants=docker.service network-online.target${dipendenze}
After=docker.service network-online.target${dipendenze}

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${dir}
ExecStart=${docker_bin} compose up -d --wait
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF
	if [[ -f "$file" ]] && cmp -s "$tmp" "$file" && systemctl is-enabled --quiet "${nome}.service" 2>/dev/null; then
		rm -f "$tmp"
		info "Unit systemd ${nome}.service già installata e aggiornata."
		return 0
	fi
	# L'utente delle app (es. agesci) di norma non è sudoer: in quel caso non si fallisce,
	# si indica il comando che l'amministratore deve eseguire (rigenera la stessa unit come root).
	if (( EUID != 0 )) && ! sudo -n true 2>/dev/null; then
		rm -f "$tmp"
		avviso "La unit systemd ${nome}.service va installata o aggiornata da un amministratore:"
		avviso "  sudo bash -c 'cd ${dir} && source scripts/_comune.sh && installa_servizio_systemd ${nome}${dipendenze}'"
		return 0
	fi
	info "Installo la unit systemd ${nome}.service."
	come_root install -m 644 "$tmp" "$file"
	rm -f "$tmp"
	come_root systemctl daemon-reload
	come_root systemctl enable --quiet "${nome}.service"
}

# Attende che tutti i servizi indicati siano "healthy" (timeout in secondi)
attendi_salute() {
	local timeout="$1"; shift
	local fine=$((SECONDS + timeout)) servizio id stato tutti_ok
	info "Attendo che i servizi siano healthy: $*"
	while (( SECONDS < fine )); do
		tutti_ok=1
		for servizio in "$@"; do
			id="$(docker compose ps -q "$servizio")"
			stato="$( [[ -n "$id" ]] && docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" || echo assente)"
			[[ "$stato" == "healthy" ]] || tutti_ok=0
		done
		(( tutti_ok )) && { info "Tutti i servizi sono healthy."; return 0; }
		sleep 5
	done
	docker compose ps >&2
	errore "Timeout: servizi non healthy dopo ${timeout}s. Controllare: docker compose logs"
}
