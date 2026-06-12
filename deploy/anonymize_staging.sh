#!/usr/bin/env bash
# Ripristina un dump di produzione nel DB staging e anonimizza i dati sensibili.
#
# Uso:
#   ./deploy/anonymize_staging.sh <dump_file.sql>
#
# Il dump va generato sulla macchina di produzione con:
#   docker compose --env-file .env.prod exec db \
#     pg_dump -U plancia plancia > prod_dump_$(date +%Y%m%d).sql
#
# Variabili d'ambiente lette da .env.staging (o dall'ambiente corrente):
#   POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
#
# Lo script va eseguito sulla macchina host, con i container staging attivi.

set -euo pipefail

DUMP_FILE="${1:-}"
if [[ -z "$DUMP_FILE" || ! -f "$DUMP_FILE" ]]; then
  echo "Uso: $0 <dump_file.sql>" >&2
  exit 1
fi

# Legge variabili da .env.staging se non già nell'ambiente
if [[ -f .env.staging ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.staging
  set +a
fi

DB="${POSTGRES_DB:-plancia_staging}"
USER="${POSTGRES_USER:-plancia_staging}"
COMPOSE_FILE="docker-compose.staging.yml"
EXEC="docker compose -f $COMPOSE_FILE --env-file .env.staging exec -T db"

echo "==> Ripristino dump in $DB..."
$EXEC psql -U "$USER" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" "$DB"
$EXEC psql -U "$USER" "$DB" < "$DUMP_FILE"

echo "==> Anonimizzazione dati sensibili..."
$EXEC psql -U "$USER" "$DB" <<'SQL'

-- accounts_user: email e password
UPDATE accounts_user
SET
  email      = 'utente_' || id || '@staging.invalid',
  first_name = 'Nome' || id,
  last_name  = 'Cognome' || id,
  -- Reset password a un hash non funzionante (nessun accesso con password originale)
  password   = 'invalid'
WHERE email NOT LIKE '%@staging.invalid';

-- allauth: email address collegate agli utenti
UPDATE account_emailaddress
SET email = 'utente_' || user_id || '@staging.invalid';

-- allauth: social account (rimuove token e dati OAuth)
UPDATE socialaccount_socialaccount
SET
  uid        = 'staging_uid_' || id,
  extra_data = '{}'::jsonb;

-- org_socio: dati anagrafici dei soci
UPDATE org_socio
SET
  nome        = 'Nome' || id,
  cognome     = 'Cognome' || id,
  email       = CASE
                  WHEN email = '' THEN ''
                  ELSE 'socio_' || id || '@staging.invalid'
                END,
  cellulare   = '',
  data_nascita = NULL;

-- diaries_anagrafica: dati CRP e CSQ nel diario
UPDATE diaries_anagrafica
SET
  crp_nome    = 'NomeCRP' || id,
  crp_cognome = 'CognomeCRP' || id,
  crp_email   = CASE WHEN crp_email = '' THEN '' ELSE 'crp_' || id || '@staging.invalid' END,
  crp_cell    = '',
  csq_nome    = 'NomeCSQ' || id,
  csq_cognome = 'CognomeCSQ' || id,
  csq_email   = CASE WHEN csq_email = '' THEN '' ELSE 'csq_' || id || '@staging.invalid' END,
  csq_cell    = '';

-- diaries_membrosq: nomi dei membri della squadriglia
UPDATE diaries_membrosq
SET nome = 'Membro ' || id;

SQL

echo "==> Anonimizzazione completata."
echo ""
echo "    ATTENZIONE: nessun account è ora accessibile con le credenziali originali."
echo "    Creare un superuser staging con:"
echo "    docker compose -f $COMPOSE_FILE --env-file .env.staging run --rm web \\"
echo "      uv run python manage.py createsuperuser"
