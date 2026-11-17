#!/usr/bin/env bash
# Prima installazione di Plancia sul server.
# Prerequisito: agesci-campania-web-frontend già installato (rete agesci-proxy esistente).
#
# Uso:  scripts/installa.sh
#       PLANCIA_ADMIN_EMAIL=x@y scripts/installa.sh   (senza domande)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_comune.sh
source scripts/_plancia.sh

richiedi_comandi docker git openssl
docker network inspect "$RETE_PROXY" >/dev/null 2>&1 \
	|| errore "Rete $RETE_PROXY mancante: installare prima agesci-campania-web-frontend."

# --- .env ---
if [[ -f .env ]]; then
	info ".env già presente, non lo modifico."
else
	info "Creo .env da .env.template con segreti nuovi."
	cp .env.template .env
	chmod 600 .env
	imposta_var DJANGO_SECRET_KEY "$(openssl rand -base64 60 | tr -d '\n')"
	# Finisce dentro DATABASE_URL: niente / + = che andrebbero codificati
	imposta_var POSTGRES_PASSWORD "$(openssl rand -base64 36 | tr -d '\n/+=')"
fi
for v in DJANGO_SECRET_KEY POSTGRES_PASSWORD ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS BASE_URL; do
	[[ -n "$(leggi_var "$v")" ]] || errore "$v vuota in .env."
done
controlla_var_nuove

# --- Versione: si installa una release (tag vX.Y.Z), poi si aggiorna con scripts/aggiorna.sh ---
git fetch --tags --quiet || avviso "Non riesco a scaricare i tag da GitHub."
if ! git describe --tags --exact-match --match 'v[0-9]*' >/dev/null 2>&1; then
	ultima="$(git tag -l 'v[0-9]*' --sort=-v:refname | head -1)"
	avviso "Il repo non è su una release (tag vX.Y.Z)."
	[[ -z "$ultima" ]] || avviso "Ultima release: $ultima (git checkout $ultima e rilanciare)."
fi

# --- Cartelle (create dall'utente del repo: i container girano con lo stesso uid) ---
mkdir -p logs backups aggiornamenti/log

# --- Avvio (le migrazioni le applica l'entrypoint del container web) ---
info "Costruisco l'immagine di Plancia e scarico le altre."
costruisci_immagini --pull
docker compose pull --ignore-buildable
docker compose up -d
attendi_salute 600 "${SERVIZI_SALUTE[@]}"

# --- Dominio del Site Django (link nelle email di allauth) ---
dominio="$(leggi_var ALLOWED_HOSTS | cut -d, -f1)"
manage shell -c "from django.contrib.sites.models import Site; Site.objects.update_or_create(pk=1, defaults={'domain': '$dominio', 'name': 'Plancia'})"
info "Site Django impostato su $dominio."

# --- Primo amministratore (solo se non ne esiste nessuno) ---
password_admin=""
email_admin=""
if [[ "$(manage shell -c 'from apps.accounts.models import User; print(User.objects.filter(is_superuser=True).exists())' | tail -n 1)" != "True" ]]; then
	email_admin="${PLANCIA_ADMIN_EMAIL:-}"
	[[ -n "$email_admin" ]] || read -rp "Email del primo amministratore di Plancia: " email_admin
	[[ -n "$email_admin" ]] || errore "Email dell'amministratore obbligatoria."
	password_admin="$(openssl rand -base64 18 | tr -d '\n')"
	# -e senza valore: la password passa dall'ambiente, non dalla riga di comando
	DJANGO_SUPERUSER_PASSWORD="$password_admin" docker compose exec -T -e DJANGO_SUPERUSER_PASSWORD web \
		uv run python manage.py createsuperuser --noinput --email "$email_admin" --username "$email_admin"
	# Email già verificata: con ACCOUNT_EMAIL_VERIFICATION="mandatory" il login resterebbe
	# in attesa della conferma, e l'invio di email non è ancora configurato
	manage shell -c "from allauth.account.models import EmailAddress; from apps.accounts.models import User; u = User.objects.get(email='$email_admin'); EmailAddress.objects.update_or_create(user=u, email=u.email, defaults={'verified': True, 'primary': True})"
	info "Creato l'amministratore $email_admin."
else
	info "Esiste già un amministratore, non ne creo altri."
fi

# --- Avvio automatico al boot (dopo il reverse proxy) e backup notturno ---
# Sestante non è una dipendenza d'avvio: serve solo al login.
installa_servizio_systemd plancia "$UNIT_PROXY"
installa_backup_systemd
installa_aggiornamenti_systemd

cat <<EOF

Plancia è attiva (rete $RETE_PROXY, alias plancia-nginx:80).
EOF
if [[ -n "$password_admin" ]]; then
	cat <<EOF

  Amministratore:  $email_admin  /  $password_admin
  (mostrata solo ora: annotarla; al primo accesso Plancia chiede di configurare la MFA)
EOF
fi
mancanti="$(credenziali_mancanti | tr '\n' ' ')"
if [[ -n "$mancanti" ]]; then
	avviso "Variabili ancora vuote in .env: $mancanti"
fi
cat <<EOF

Passi successivi:
  0. Avvio al boot: systemctl status plancia plancia-backup.timer (se sopra sono indicati
     comandi per l'amministratore, vanno eseguiti da un utente sudoer)
  1. DNS: ${dominio} → IP di questo server
  2. In agesci-campania-web-frontend aggiungere caddy/sites/plancia.caddy:

       # Plancia — Guidoncini Verdi (Branca E/G)
       # Repo: https://github.com/AGESCI-Campania/plancia
       ${dominio} {
       	import comune
       	reverse_proxy plancia-nginx:80
       }

     commit, push, poi /opt/agesci-campania-web-frontend/scripts/aggiorna.sh
  3. SSO Sestante: client ID e secret del provider "Plancia AGESCI Campania" da
     https://auth.agescicampania.net/if/admin/#/core/providers → Plancia AGESCI Campania → modifica
     in .env come SOCIAL_SESTANTE_CLIENT_ID e SOCIAL_SESTANTE_CLIENT_SECRET, poi docker compose up -d
     (callback registrata nel blueprint: https://${dominio}/accounts/oidc/sestante/login/callback/)
  4. ADMIN_EMAILS in .env (notifiche errori), poi docker compose up -d
  5. https://${dominio} — login come amministratore, MFA, poi Impostazioni (email, Drive)
EOF
