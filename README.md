# Plancia

[![Python](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1%2B-092E20.svg?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-42b883.svg?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-6%20alpha-7952B3.svg?logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![django-ninja](https://img.shields.io/badge/API-django--ninja-009688.svg)](https://django-ninja.dev/)
[![uv](https://img.shields.io/badge/packaged%20with-uv-DE5FE9.svg?logo=uv&logoColor=white)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Piattaforma di gestione dei **Guidoncini Verdi** — AGESCI Campania, Branca E/G.
Le squadriglie compilano il *Diario di Bordo*, i capi lo integrano, gli Incaricati EG valutano e
pubblicano l'esito; output in PDF ed Excel, file su Google Drive. Dalla 3.0 l'interfaccia è una
SPA Vue installabile come app (PWA), compilabile anche offline; il backend Django espone solo l'API.

> Specifica completa: [`docs/Plancia_Progettazione.md`](docs/Plancia_Progettazione.md).
> Guida per l'implementazione assistita: [`CLAUDE.md`](CLAUDE.md).

## Stack
**Backend** (API-only): Python ≥ 3.14 · Django ≥ 6.1 · PostgreSQL ≥ 18 · Redis + Celery ·
django-ninja (`/api/v1`, OpenAPI) · django-allauth headless (login, MFA con TOTP e passkey, social,
SSO Sestante) · django-guardian · django-axes · WeasyPrint · openpyxl · odfpy · Google Drive (OAuth).
**Frontend** (`frontend/`): Vue 3.5 · TypeScript 6 · Vite 8 · vue-router 5 · Pinia 4 · Bootstrap 6
(alpha, tema AGESCI 3.0) · Dexie (offline) · vite-plugin-pwa · Tiptap · Vitest · Playwright.
Gestione dipendenze con **uv** e **npm**; ambiente opzionale con **mise**.

## Prerequisiti
- **uv** ([astral.sh/uv](https://docs.astral.sh/uv/)) — obbligatorio.
- **Node.js** ≥ 24 + npm — per il frontend.
- **Docker** + Docker Compose — per database/redis in dev e per la produzione.
- Python 3.14 — via **mise** (opzionale) oppure di sistema.
- *(opzionale)* **mise** ([mise.jdx.dev](https://mise.jdx.dev)) per toolchain e task.

## Avvio rapido (sviluppo)
Il database e Redis girano in Docker; **Django gira sull'host con `uv run`**.

```bash
# 1. dipendenze
uv sync                      # oppure: mise run install

# 2. env di sviluppo
cp .env.dev.example .env.dev

# 3. servizi dockerizzati (db + redis + mailpit)
docker compose -f docker-compose.dev.yml up -d             # oppure: mise run up

# 4. migrazioni + server
uv run python manage.py migrate                            # oppure: mise run migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver 0.0.0.0:8000             # oppure: mise run dev

# 5. frontend (in un altro terminale): http://localhost:5173
cd frontend && npm install && npm run dev
```
La SPA in sviluppo gira su Vite (`:5173`) e inoltra a Django (`:8000`) API, allauth, admin e
callback (`frontend/vite.config.ts`). Controlli del frontend: `npm run typecheck`, `npm run lint`,
`npm test`, `npm run e2e`; tipi dell'API rigenerati con `npm run api:tipi`.

**Email in dev**: le email vengono intercettate da **Mailpit** — nessuna email reale viene inviata.
Apri `http://localhost:8025` per vedere tutti i messaggi nella web UI.

Celery in dev è in modalità *eager* (i task girano in-process). Per provarlo come servizio reale:
`uv run celery -A config worker -l info` (o `mise run worker`).

### Con mise (opzionale)
`mise install` installa Python 3.14 + uv. I task disponibili: `install`, `up`, `down`,
`makemigrations`, `migrate`, `dev`, `worker`, `lint`, `format`, `test`.

## PyCharm Professional
1. Apri la cartella come progetto.
2. **Interprete**: dopo `uv sync`, imposta l'interprete su `./.venv/bin/python`
   (*Settings → Project → Python Interpreter → Add → Existing*). Le versioni recenti di PyCharm
   riconoscono direttamente i progetti uv.
3. **Django support**: *Settings → Languages & Frameworks → Django* → abilita, root = cartella del
   progetto, settings = `config/settings/dev.py`, manage script = `manage.py`.
4. **Run configuration** condivise (cartella `.run/`): `runserver`, `manage.py migrate`,
   `celery worker` compaiono già nel menu Run (potrebbe servire confermare l'interprete).
5. Database e Redis: avviali con `docker compose -f docker-compose.dev.yml up -d db redis`.

## Produzione
Plancia gira in Docker sul server delle piattaforme `*.agescicampania.net`, dietro il reverse
proxy **Caddy** di [`agesci-campania-web-frontend`](https://github.com/AGESCI-Campania/agesci-campania-web-frontend)
(TLS Let's Encrypt, unico a pubblicare le porte 80/443). Login SSO con
[**Sestante**](https://github.com/AGESCI-Campania/sestante) (`https://auth.agescicampania.net`),
accanto al login locale. Regole di integrazione:
[frontend](https://raw.githubusercontent.com/AGESCI-Campania/agesci-campania-web-frontend/main/docs/INTEGRAZIONE.md) ·
[SSO](https://raw.githubusercontent.com/AGESCI-Campania/sestante/main/docs/INTEGRAZIONE-SSO.md).

| | |
|---|---|
| URL | `https://plancia.agescicampania.net` |
| Repo sul server | `/opt/plancia`, utente `agesci` (gruppo `docker`, senza sudo) |
| Ingresso | servizio `nginx` (solo HTTP) su rete esterna `agesci-proxy`, alias `plancia-nginx:80`; nessuna porta pubblicata |
| Servizi | `nginx` (SPA costruita + proxy, `frontend/Dockerfile`), `web` (gunicorn: API, admin, callback), `worker`, `beat`, `db` (PostgreSQL 18), `redis`; profili facoltativi `mailpit`, `flower` |
| Variabili | `.env` (da `.env.template`, `chmod 600`, mai nel repo) |
| Avvio al boot | unit systemd `plancia.service` (`docker compose up -d --wait`, dopo `agesci-campania-web-frontend.service`) + `restart: unless-stopped` |
| Backup | `scripts/backup.sh` ogni notte (timer `plancia-backup.timer`) in `backups/` |
| Aggiornamento dal web | `plancia-aggiorna.path` → `scripts/esegui-aggiornamento.sh` (richieste da Impostazioni → Aggiornamenti, solo Admin) |

**Prima installazione** (prerequisito: frontend già installato, rete `agesci-proxy` esistente):
```bash
sudo install -d -o agesci -g agesci /opt/plancia          # come amministratore
sudo -iu agesci
git clone https://github.com/AGESCI-Campania/plancia.git /opt/plancia
cd /opt/plancia && git checkout "$(git tag -l 'v[0-9]*' --sort=-v:refname | head -1)"
scripts/installa.sh
```
Il server resta sempre su una **release** (tag `vX.Y.Z`, "detached HEAD").
`installa.sh` crea `.env` con segreti nuovi (non tocca un `.env` esistente), costruisce
le immagini (una alla volta), avvia lo stack (le migrazioni le applica l'entrypoint del container `web`), attende
che i servizi siano `healthy`, crea il primo amministratore (password mostrata una sola volta),
installa le unit systemd e stampa i passi manuali: blocco `caddy/sites/plancia.caddy` da
aggiungere al frontend, client id/secret di Sestante, `ADMIN_EMAILS`. Senza sudo le unit non
vengono installate: lo script stampa il comando da far eseguire a un amministratore.

**Aggiornamento a una nuova release** (da terminale, oppure dagli Admin in Impostazioni →
Aggiornamenti, che usano lo stesso script):
```bash
sudo -iu agesci
cd /opt/plancia && scripts/aggiorna.sh            # ultima release; oppure: scripts/aggiorna.sh v3.1.0
```
Rifiuta di partire con modifiche locali, mostra le novità da `CHANGELOG.md`, si ferma se la
release richiede variabili nuove in `.env`, mette Plancia in manutenzione, fa il backup del
database (`backups/`, ultimi 10), costruisce le immagini tenendo quelle in uso come
"precedenti", riavvia e attende `healthy`. Se la versione nuova non risponde torna da sola alla
precedente (senza ricostruire); se il database era già stato migrato resta in manutenzione e
indica il backup da ripristinare. Mai lanciarlo con `sudo` o da root.

**Aggiornamento non riuscito con il database cambiato:** `aggiorna.sh` ha già rimesso il codice
e le immagini della versione precedente, fermato `web`, `worker`, `beat` (e `flower`) e lasciato
acceso `nginx` (la SPA si carica, le API rispondono con la pagina di servizio non disponibile).
Non riavviare i servizi prima di aver ripristinato il backup indicato nel messaggio
(`backups/plancia-db-…-pre-<versione>.sql.gz`):
```bash
sudo -iu agesci
cd /opt/plancia
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
gunzip -c backups/<file indicato> | docker compose exec -T db sh -c 'psql -q -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose up -d --wait
docker compose exec -T web uv run python manage.py manutenzione disattiva
```
Il backup è stato fatto con la manutenzione già attiva: l'ultimo comando serve sempre. Poi
segnalare il problema della release con il log dell'aggiornamento.

**Rilascio di una versione** (dal Mac, *prima* dell'aggiornamento del server): versione in
`pyproject.toml`, sezione in `CHANGELOG.md`, commit su `main`, poi `git tag vX.Y.Z && git push
origin vX.Y.Z` e `gh release create vX.Y.Z` con le note della sezione del changelog.

**Diagnostica:**
```bash
cd /opt/plancia
docker compose ps                         # stato e salute dei servizi
docker compose logs --tail 100 web worker # stdout gunicorn / celery
tail -f logs/plancia.log                  # log Django (errori 500, warning)
systemctl status plancia plancia-backup.timer plancia-aggiorna.path
ls aggiornamenti/log/                     # log degli aggiornamenti avviati dal web
```

La **SPA** è costruita nell'immagine `plancia-nginx` (fallback a `index.html` per i link diretti,
service worker e manifest senza cache); gli statici dell'admin Django sono serviti da WhiteNoise
e generati nell'immagine `web`. I **media** (upload foto)
usano il volume `plancia_media`. Dopo ogni modifica a `.env`: `docker compose up -d` (ricrea i
container; `restart` non rilegge le variabili).

**CORS**: solo per l'app mobile (`/api/v1`, `/_allauth/app`), con `CORS_ALLOWED_ORIGINS` nell'env.

## Struttura
```
config/      progetto Django (settings split, urls, celery, wsgi/asgi)
apps/        app di dominio (accounts, org, editions, diaries, evaluations,
             notifications, storage_drive, exports, helpdesk, stats,
             siteconfig, imports, api)
scripts/     installa.sh, aggiorna.sh, backup.sh (+ funzioni condivise _comune.sh, _plancia.sh)
deploy/      entrypoint del container, conf dell'nginx interno (SPA + proxy)
frontend/    SPA Vue (Vite), PWA, Dockerfile dell'immagine nginx
fixtures/    CSV sintetici per provare gli import (nessun dato reale)
logs/        log applicativi + log email simulati (logs/email/)
docs/        specifica di progetto e documentazione API (docs/api/)
.run/        run configuration condivise PyCharm
```

## Qualità e test
Backend: `uv run ruff check .` · `uv run ruff format .` · `uv run mypy .` · `uv run pytest`
(API per ruolo in `apps/api/tests/`, dominio FSM/visibilità/permessi/servizi nelle singole app;
il rate limit dell'API è disattivato nei test da `conftest.py`). `pre-commit install`.

Frontend (`frontend/`): `npm run typecheck` · `npm run lint` · `npm test` (Vitest) ·
`npm run e2e` (Playwright, desktop e iPhone, contro lo stack di sviluppo; i flussi che richiedono
utenti di prova leggono le credenziali da variabili `PLANCIA_E2E_*` e si saltano se mancano).

## Import dei tracciati
Con dati sintetici (vedi `fixtures/`):
```bash
uv run python manage.py import_coca    fixtures/sample_coca.csv    --dry-run
uv run python manage.py import_ragazzi fixtures/sample_ragazzi.csv --dry-run
uv run python manage.py import_squadriglie fixtures/sample_evento.csv  --edizione 1 --dry-run
```
Sorgenti: **Co.Ca. (BuonaStrada)** (capi → tutti i ruoli tranne Capo Squadriglia),
**ragazzi (BuonaStrada)** (solo Capi Squadriglia, senza email),
**Squadriglie iscritte (BuonaCaccia)** (anagrafiche diari; collega Capo Squadriglia via codice socio
e Capo Reparto via email referente). Mappatura completa in `docs/Plancia_Progettazione.md`, Appendice D.
**I CSV reali non vanno versionati** (dati di minori).

Se l'email di un Capo Reparto non corrisponde a nessun Socio già importato, `import_squadriglie`
crea automaticamente un **record provvisorio** con codice `tmpNNNNN` e i dati del tracciato (nome,
cognome, email). Il record è sostituito dalla riconciliazione manuale/automatica nella pagina import.
Questo garantisce che ogni diario abbia sempre un Capo Reparto, anche prima della riconciliazione.

**Gestione errori per record**: se un singolo record causa un errore DB (valore troppo lungo,
violazione di unicità, ecc.) viene marcato `SCARTATA` nello storico con il messaggio di errore come
nota — l'import **non si interrompe** e prosegue sui record successivi. I record scartati con il
relativo messaggio di errore sono visibili nel dettaglio del log (`/import/<pk>/`) e scaricabili come
CSV (`/import/<pk>/scarti.csv`).

**Creazione account durante import**: `import_squadriglie` crea automaticamente gli account (con
password inutilizzabile) per Capo Squadriglia e Capo Reparto già presenti nel tracciato. Gli account
vengono attivati tramite il flusso inviti (`/notifiche/inviti/`).

**Box di avvio import**: le schede per lanciare i tre import (Co.Ca., Ragazzi, Squadriglie iscritte)
si trovano nella pagina **`/import/`**, non più in `/impostazioni/`.

## Impostazioni di piattaforma (solo Admin/Segreteria/IABR)
Pagina `/impostazioni/` organizzata in sezioni:

| Sezione | Contenuto |
|---|---|
| **Identità** | Titolo · Sottotitolo (visualizzati nella navbar) |
| **Footer** | Testo rich text · Fino a 4 link tipizzati con etichetta opzionale · link Manuale fisso come ultimo elemento |
| **Posta elettronica** | Nome mittente · Indirizzo from · Modalità email · Provider · API key · SMTP · Gmail OAuth2 · Test invio |
| **Sicurezza** | MFA obbligatoria · Protezione brute-force axes · IP bloccati |
| **Allegati** | Dimensione massima immagini upload (default 1024px) |
| **Diagnostica** | Manutenzione · Debug toolbar · Link Flower/Mailpit |
| **Strumenti** | Link Cache PDF (`/impostazioni/cache-pdf/`) · Log export (`/impostazioni/log-export/`) |
| **Import tracciati** | Avvia import Co.Ca. / Ragazzi / Evento + link storico |
| **Pagine legali** | Privacy Policy · Condizioni del Servizio · Carica testo predefinito |
| **Template email** | Elenco chiavi con stato (DB / file default) · Editor rich text |

**Cache PDF** (`/impostazioni/cache-pdf`): lista PDF in cache per edizione, invalidazione singola/massiva,
generazione massiva con task Celery (email aggiornamento ogni 10 diari; blocca PDF singoli durante la generazione).
Pulsante **Interrompi** per fermare ordinatamente una generazione in corso.

**Log export** (`/impostazioni/log-export`): storico task PDF/Excel con errori completi (traceback in modale).

**Template email**: editor Tiptap con segnaposti, immagini, vista HTML e anteprima (i template con
HTML complesso si aprono nel sorgente, intatto). Se il template non è in DB usa il file di default
`templates/mail/<chiave>.html`; il pulsante **"Importa da file"** carica quel file come punto di partenza.

**Provider email transazionali** (tracking bounce/errori): selezionare un provider (Brevo,
Mailgun, MailerSend, Postmark, SendGrid, SparkPost, Amazon SES) e inserire l'API key. Il webhook
di tracking va configurato nel pannello del provider con l'URL `/anymail/webhook/`.
Guida completa: [`docs/guide/email_provider.md`](docs/guide/email_provider.md).

**Modalità Mailpit (debug)**: selezionare la modalità "Mailpit" per intercettare tutte le email
senza inviarle ai destinatari reali. Richiede il profilo Docker `mailpit`. Le email intercettate
sono visibili su `/mailadmin/` (solo Admin/staff).

**Aggiornamenti** (`/impostazioni/aggiornamenti`, solo Admin): versione installata e ultima release
su GitHub (controllo giornaliero), note di rilascio, pulsante "Aggiorna" con riautenticazione,
avanzamento e log in tempo reale, storico. Lato server lo esegue `scripts/esegui-aggiornamento.sh`
(unit `plancia-aggiorna.path`); il container non ha accesso a Docker.

## Home page
La home mostra l'edizione attiva più recente (stato `Aperta` o `In valutazione`) con i riepiloghi
per ruolo. Se non ci sono edizioni attive mostra una pagina informativa con link per creare
un'edizione (solo staff) o aprire una richiesta helpdesk.

Il **DEBUG** reale è governato da `DJANGO_DEBUG` in `.env` e **richiede `docker compose up -d`**;
i flag in pagina gestiscono solo debug-toolbar (admin) e verbosità di logging.

## Backup periodico
Ogni notte alle 02:30 il timer systemd `plancia-backup.timer` esegue `scripts/backup.sh`
(installato da `installa.sh`/`aggiorna.sh`): un unico archivio con dump del database, `.env` e
media, in `BACKUP_DIR` (default `backups/`), conservato `BACKUP_GIORNI` giorni (default 14).
Si può lanciare anche a mano; la procedura di ripristino è in testa allo script.

## Impersonazione utenti
Admin e Segreteria possono impersonare altri utenti (assistenza/diagnosi) **solo** verso ruoli con
rango ≤ al proprio — la Segreteria non può impersonare un Admin. Via **django-hijack**, con banner di
sessione e audit, avviata dalla pagina dell'utente (`POST /api/v1/utenti/{id}/impersona`). Logica in
`apps/accounts/roles.py` (`can_hijack`) e `apps/accounts/services.py`.

## Archiviazione e retention (edizioni chiuse)
```bash
uv run python manage.py archivia_edizione --edizione 1 --genera           # PDF + Excel su Drive
uv run python manage.py archivia_edizione --edizione 1 --purga --conferma # elimina le foto, archivia
```
Conserva su Drive i PDF dei diari e l'Excel esiti; ripulisce la piattaforma dai dati pesanti (foto),
mantenendo i link esterni come testo.

## Interfaccia e versioni
La sidebar (drawer su telefono) mostra le voci consentite al ruolo attivo secondo i flag calcolati
dal backend (`/api/v1/me`, `menu`); dal menu utente si cambia ruolo, si apre il profilo, la sicurezza
(TOTP, passkey, codici di recupero) e si esce. Il footer mostra la versione dell'**app** installata
e quella del **server**: se l'app è indietro compare la finestra "Aggiornamento disponibile"
(rimandabile), che prima invia le modifiche fatte offline. Le modifiche ai moduli e le foto fatte
senza rete restano sul dispositivo (badge "N da inviare") e partono alla riconnessione.

## Manuale d'uso

La documentazione operativa per ruolo si trova in `docs/manuale/`:

| File | Ruolo |
|---|---|
| [`index.md`](docs/manuale/index.md) | Panoramica, ruoli, moduli, modalità di accesso |
| [`csq.md`](docs/manuale/csq.md) | Capo Squadriglia — primo accesso (codice socio), compilazione Diario |
| [`crp.md`](docs/manuale/crp.md) | Capo Reparto — distribuzione link CSQ, relazione finale |
| [`pgv.md`](docs/manuale/pgv.md) | Pattuglia Guidoncini Verdi — valutazione |
| [`incaricato.md`](docs/manuale/incaricato.md) | Incaricato EG — assegnazione, conferma, pubblicazione |
| [`segreteria.md`](docs/manuale/segreteria.md) | Segreteria — Gestione Inviti, import, edizioni, impostazioni |
| [`admin.md`](docs/manuale/admin.md) | Admin — MFA, social auth, Google Drive OAuth, archiviazione |

Le immagini sono in `docs/manuale/screenshots/`; in Plancia 3 si rigenerano con Playwright
sulla SPA (gli script Selenium dell'interfaccia Django 2.x sono stati rimossi).

## Manuale — generazione PDF

GitHub Actions genera **cinque PDF separati** ad ogni nuova release e li allega come asset
(`.github/workflows/release-manual.yml`):

| PDF | Contenuto |
|---|---|
| `plancia_manuale.pdf` | Manuale completo (tutti i ruoli) |
| `manuale_csq.pdf` | Solo Capo Squadriglia |
| `manuale_crp.pdf` | Solo Capo Reparto |
| `manuale_valutazione.pdf` | Pattuglia GV + Incaricato EG |
| `manuale_amministrazione.pdf` | Segreteria + Incaricato EG + Admin |

Per generarli localmente con [pandoc](https://pandoc.org/) (usa il file defaults condiviso):

```bash
cd docs/manuale
DATE=$(date +'%B %Y')

# Manuale completo
pandoc --defaults pandoc-defaults.yaml \
  -V title="Plancia — Manuale d'uso" -V subtitle="Guidoncini Verdi · AGESCI Campania" \
  -V date="$DATE" \
  index.md csq.md crp.md pgv.md incaricato.md segreteria.md admin.md \
  -o plancia_manuale.pdf

# Oppure un singolo ruolo, es.:
pandoc --defaults pandoc-defaults.yaml \
  -V title="Plancia — Guida Capo Squadriglia" -V date="$DATE" \
  csq.md -o manuale_csq.pdf
```

I PDF sono esclusi dal repository (artefatti generati).

## Changelog

Vedi [CHANGELOG.md](CHANGELOG.md).

## Licenza
[MIT](LICENSE) — Copyright © 2026 Andrea Bruno.
