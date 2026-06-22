# Plancia

[![Python](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.0%2B-092E20.svg?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3.svg?logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![uv](https://img.shields.io/badge/packaged%20with-uv-DE5FE9.svg?logo=uv&logoColor=white)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Piattaforma di gestione dei **Guidoncini Verdi** — AGESCI Campania, Branca E/G.
Le squadriglie compilano il *Diario di Bordo*, i capi lo integrano, gli Incaricati EG valutano e
pubblicano l'esito; output in PDF ed Excel, file su Google Drive, frontend responsive e PWA.

> Specifica completa: [`docs/Plancia_Progettazione.md`](docs/Plancia_Progettazione.md).
> Guida per l'implementazione assistita: [`CLAUDE.md`](CLAUDE.md).

## Stack
Python ≥ 3.14 · Django ≥ 6.0 · PostgreSQL ≥ 17 · Redis + Celery · django-allauth (MFA, social) ·
django-guardian · django-axes · django-pwa · Bootstrap 5 · django-agesci-campania-theme 2.2.2 ·
django-bootstrap-icons · WeasyPrint · openpyxl · Google Drive (OAuth).
**PWA offline-first**: Service Worker · IndexedDB · Background Sync · resize immagini client-side.
Gestione dipendenze con **uv**; ambiente opzionale con **mise**.

## Prerequisiti
- **uv** ([astral.sh/uv](https://docs.astral.sh/uv/)) — obbligatorio.
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
uv run python manage.py makemigrations
uv run python manage.py migrate                            # oppure: mise run migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver 0.0.0.0:8000             # oppure: mise run dev
```

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
Tutto dockerizzato **tranne il reverse proxy**, che è configurabile. Lo script interattivo prepara
tutto:

```bash
./deploy/configure-prod.sh
```

Scegli:
- **modalità proxy**: `nginx-docker` (nginx nel compose) · `nginx-host` (nginx esistente) ·
  `apache-host` (Apache 2 esistente);
- **porta** dell'app (default **8000**);
- **TLS** e i parametri d'ambiente.

Lo script genera `.env.prod`, le directory `logs/` e `staticfiles/` sull'host,
il vhost per la modalità scelta (`deploy/plancia.nginx.conf` o `deploy/plancia.apache.conf`)
e il file systemd `deploy/plancia.service` per l'avvio automatico.

**Prima installazione — sequenza completa:**
```bash
./deploy/configure-prod.sh          # genera .env.prod, vhost, service

# 1. Avvia i container
docker compose --env-file .env.prod up -d

# 2. Migrazioni e static files
docker compose --env-file .env.prod exec web uv run python manage.py migrate --noinput
docker compose --env-file .env.prod exec web uv run python manage.py collectstatic --noinput
# -> staticfiles/ viene popolata sull'host e servita direttamente da nginx/Apache

# 3. Crea il primo amministratore
docker compose --env-file .env.prod exec web uv run python manage.py createsuperuser
# poi accedi a /admin/ e imposta il ruolo Admin da Impostazioni → Utenti

# 4. Installa il service systemd per l'avvio automatico (opzionale)
sudo cp deploy/plancia.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now plancia
```

**Deploy aggiornamenti:**
```bash
git pull
sudo systemctl reload plancia   # rebuild immagine + ricrea container + migrate automatico
```

Oppure senza systemd:
```bash
git pull
docker compose --env-file .env.prod build web
docker compose --env-file .env.prod up -d web
```

Le migrazioni vengono applicate automaticamente all'avvio del container (`deploy/entrypoint.sh`).
`systemctl restart` riavvia i container **senza** rebuild: usare solo per riavvii di emergenza.

**Variabili d'ambiente opzionali** da aggiungere a `.env.prod` per le integrazioni Google:
```bash
# Gmail SMTP OAuth2 (se si usa Gmail come backend SMTP)
GOOGLE_GMAIL_SMTP_REDIRECT_URI=https://tuo-dominio.org/impostazioni/gmail-smtp/oauth/callback/
```

**Diagnostica:**
```bash
tail -f logs/plancia.log                        # log Django (errori 500, warning)
docker compose --env-file .env.prod logs -f web # stdout gunicorn
```

Template vhost: `deploy/nginx.vhost.tpl`, `deploy/apache.vhost.tpl`,
`deploy/nginx/default.conf` (nginx dockerizzato).

I **static files** (`/static/`) sono serviti direttamente da nginx/Apache dalla directory
`staticfiles/` sull'host (montata in `/app/staticfiles` nel container via volume bind).
I **media** (upload foto) usano il volume named `plancia_media`.

## Struttura
```
config/      progetto Django (settings split, urls, celery, wsgi/asgi)
apps/        app di dominio (accounts, org, editions, diaries, evaluations,
             notifications, storage_drive, exports, helpdesk, stats,
             siteconfig, imports)
deploy/      Dockerfile-related, vhost template, configure-prod.sh, conf nginx, backup.sh
fixtures/    CSV sintetici per provare gli import (nessun dato reale)
logs/        log applicativi + log email simulati (logs/email/)
docs/        specifica di progetto
.run/        run configuration condivise PyCharm
```

## Qualità
`uv run ruff check .` · `uv run ruff format .` · `uv run pytest` · `pre-commit install`.

## Test

| Suite | Test | Esito | Note |
|---|---|---|---|
| **accounts** — login form | 12 | ✅ pass | Form Bootstrap, validazioni, allauth |
| **accounts** — MFA enforcement | 18 | ✅ pass | Middleware, bypass dev, ruoli con MFA |
| **accounts** — ruoli e nomina | 21 | ✅ pass | Permessi, ranghi, puo_nominare, staff diretto |
| **diaries** — FSM | 16 | ✅ pass | Transizioni stato, riapertura |
| **diaries** — visibilità | 6 | ✅ pass | Accesso a moduli per ruolo |
| **diaries** — cambio referenti | 29 | ✅ pass | CambiaCsqView, CambiaCrpView, bulk |
| **diaries** — Selenium E2E | 15 | ✅ pass | Chrome headless, Tom Select, sessione |
| **diaries** — moduli_csq_completi | 8 | ✅ pass | Logica NUOVO/RINNOVO |
| **diaries** — eliminazione allegati | 5 | ✅ pass | Permessi per stato e ruolo |
| **diaries** — dilazione e nuovi campi | 8 | ✅ pass | Context dilazione, PostoAzione chi+cosa, chi specialità |
| **evaluations** — flussi di valutazione | 3 | ✅ pass | Flusso diretto da INVIATO, override proposta PGV |
| **Totale** | **141** | **✅ 141/141** | `uv run pytest` — 2026-06-10 (v1.16.0) |

I test Selenium (12) usano **Django LiveServer** + **Selenium 4** con ChromeDriver scaricato
automaticamente da Selenium Manager. Coprono:
- Visibilità pulsanti "Cambia Capo Squadriglia / Cambia Capo Reparto" per ruolo e stato diario
- Compilazione form cambio CSQ e CRP (autenticazione via cookie di sessione, submit, redirect, verifica DB)
- Bulk cambio Capo Reparto per reparto

Eseguire con Chrome installato: `uv run pytest apps/diaries/tests/test_selenium.py`.

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

**Cache PDF** (`/impostazioni/cache-pdf/`): lista PDF in cache per edizione, invalidazione singola/massiva,
generazione massiva con task Celery (email aggiornamento ogni 10 diari; blocca PDF singoli durante la generazione).
Pulsante **Interrompi** per fermare ordinatamente una generazione in corso.

**Log export** (`/impostazioni/log-export/`): storico task PDF/Excel con errori completi (traceback in modale).

**Template email**: editor rich text (TinyMCE). Se il template non è in DB usa il file di default
`templates/mail/<chiave>.html`; il pulsante **"Importa da file"** carica quel file come punto di partenza.

**Provider email transazionali** (tracking bounce/errori): selezionare un provider (Brevo,
Mailgun, MailerSend, Postmark, SendGrid, SparkPost, Amazon SES) e inserire l'API key. Il webhook
di tracking va configurato nel pannello del provider con l'URL `/anymail/webhook/`.
Guida completa: [`docs/guide/email_provider.md`](docs/guide/email_provider.md).

**Modalità Mailpit (debug)**: selezionare la modalità "Mailpit" per intercettare tutte le email
senza inviarle ai destinatari reali. Richiede il profilo Docker `mailpit`. Le email intercettate
sono visibili su `/mailadmin/` (solo Admin/staff).

Le impostazioni vengono iniettate automaticamente in ogni template tramite il context processor
`apps.siteconfig.context_processors.impostazioni` (variabile `{{ impostazioni }}`).

## Home page
La radice `/` reindirizza all'edizione attiva più recente (stato `Aperta` o `In valutazione`).
Se non ci sono edizioni attive viene mostrata una pagina informativa con link per creare un'edizione
(solo staff) o aprire una richiesta helpdesk.

Il **DEBUG** reale è governato da `DJANGO_DEBUG` in `.env.prod` e **richiede un redeploy/restart**;
i flag in pagina gestiscono solo debug-toolbar (admin) e verbosità di logging.

## Backup periodico (cron)
```bash
# notturno alle 02:30 (vedi deploy/crontab.example)
30 2 * * *  cd /srv/plancia && ./deploy/backup.sh >> /var/log/plancia_backup.log 2>&1
```
Lo script fa `pg_dump` (dal container) + gzip, archivia media/log, applica la retention (30 giorni)
e può inviare una notifica email.

## Impersonazione utenti
Admin e Segreteria possono impersonare altri utenti (assistenza/diagnosi) **solo** verso ruoli con
rango ≤ al proprio — la Segreteria non può impersonare un Admin. Via **django-hijack**, con banner di
sessione e audit. Logica in `apps/accounts/roles.py` (`can_hijack`).

## Archiviazione e retention (edizioni chiuse)
```bash
uv run python manage.py archivia_edizione --edizione 1 --genera           # PDF + Excel su Drive
uv run python manage.py archivia_edizione --edizione 1 --purga --conferma # elimina le foto, archivia
```
Conserva su Drive i PDF dei diari e l'Excel esiti; ripulisce la piattaforma dai dati pesanti (foto),
mantenendo i link esterni come testo.

## Navbar e UI

La navbar in `templates/base.html` è **role-aware**: mostra le voci rilevanti per ciascun ruolo.

| Ruolo | Voci visibili |
|---|---|
| **Admin / Incaricato EG** | Home · Diari · Helpdesk · Gestione ▾ · badge utente |
| **Segreteria** | Home · Diari · Helpdesk · Gestione ▾ (no Impostazioni/Admin) · badge utente |
| **Pattuglia GV** | Home · Diari assegnati · Helpdesk · badge utente |
| **Capo Reparto** | Home · Diari · Inviti · Helpdesk · badge utente |
| **Capo Squadriglia** | Home · Diari · Helpdesk · badge utente |

Il dropdown **Gestione** (staff) include, nella sezione "Persone", i link **Utenti** e **Inviti** (dashboard invii massivi CRP/CSQ per edizione).

Il **badge utente** (cerchio con iniziale) apre un dropdown con: Profilo, Email account,
Cambia password, Sicurezza (MFA), Esci. L'intestazione mostra nome e chip con il ruolo.

Il **brand navbar** mostra `impostazioni.titolo` (fallback "Plancia") e, se valorizzato,
`impostazioni.sottotitolo` su una riga più piccola sottostante.

Quando Admin/Segreteria impersonano un utente (django-hijack), appare un **banner arancio** fisso
in cima alla pagina con il nome dell'utente impersonato e il pulsante "Esci dall'impersonazione".

> **Nota implementativa**: `{% block %}` nei template `{% include %}` non partecipano all'ereditarietà
> Django. Il `{% block navbar %}` in `base.html` sovrascrive l'intero blocco del tema — non usare
> `{{ block.super }}` per le voci di navigazione.

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

Le immagini sono in `docs/manuale/screenshots/` e vengono generate dallo script
`docs/manuale/seed_e_screenshot.py` (richiede server in esecuzione su `localhost:8000`).

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

### v2.0.2

- **Fix icona PWA su iOS**: override di `templates/pwa.html` con `{% static %}` per `apple-touch-icon`
  e `icon-512x512` — `ManifestStaticFilesStorage` genera URL hashati che bustano la cache WebKit
  automaticamente ad ogni aggiornamento del file.

### v2.0.1

- **Pulsante indietro mobile nell'header**: nelle pagine con breadcrumb, su schermi stretti (<992px)
  compare un pulsante `‹` che riporta alla voce precedente della breadcrumb (breadcrumb-aware).

### v2.0.0 (in sviluppo — branch `v2-offline`)

**PWA offline-first**

Il Capo Squadriglia può compilare il Diario di Bordo e allegare foto anche senza connessione
(in campo, in montagna) e sincronizzare al ritorno della connettività.

- **API JSON moduli 1–5** con optimistic locking (`version` su ogni modulo): il client invia
  la versione su cui ha basato la modifica; il server rifiuta con 409 se la versione è obsoleta.
- **Service Worker** (v4): cache asset e pagine per uso offline; network-only per `/accounts/`
  e `/allauth/` (token CSRF sempre fresco); gestione bfcache iOS (`pageshow`, `visibilitychange`).
- **IndexedDB + autosave**: i moduli vengono salvati nel browser a ogni modifica; la coda di sync
  li invia al server al ritorno online.
- **Coda allegati offline**: le foto selezionate vengono ridimensionate client-side (Canvas → JPEG),
  accodate in IndexedDB, sincronizzate in automatico. Il flush processa tutti i moduli in coda,
  non solo quello della pagina attiva.
- **Auth offline**: se la sessione scade mentre si è offline, la coda viene trattenuta con banner
  "Hai modifiche in attesa — accedi per sincronizzare"; il sync riparte automaticamente al login.
- **Badge UI**: indicatore foto in sospeso nell'header; badge connessione offline; badge sync.
- **Fix iOS PWA**: CSRF al login (PKCE), bfcache restore, preview allegati con fallback locale.

---

### v1.17.1 (12/06/2026)

**Fix passkey — completamento funzionalità**
- Fix CSRF su iOS Safari dopo login Google: `PlanciaAuthenticateView` non chiama più `begin_authentication()` inutilmente per utenti senza passkey, evitando la scrittura in sessione che causava il mismatch CSRF
- Fix: aggiunto `MFA_SUPPORTED_TYPES = ["totp", "recovery_codes", "webauthn"]` nelle settings — senza questa impostazione `"webauthn"` non compariva in `SUPPORTED_TYPES` e la sezione passkey restava nascosta
- Template Bootstrap per tutte le pagine WebAuthn: aggiungi passkey, lista, rinomina, elimina
- Pulsante "Accedi con passkey" nella pagina di login con attributo `form="mfa_login"` necessario per l'associazione al form nascosto usato da `webauthn.js`

---

### v1.17.0 (12/06/2026)

**Passkey (WebAuthn)**
- Abilitato il login con passkey: Face ID, Touch ID, Windows Hello e chiavi hardware (YubiKey)
- Gli utenti possono aggiungere e gestire le passkey dalla pagina **Sicurezza (MFA)** nel menu utente
- Pulsante "Accedi con passkey" nella pagina di login (visualizzato se l'utente ha passkey registrate)
- La registrazione autonoma via passkey è disabilitata: l'account deve essere creato tramite il flusso inviti esistente
- Manuale Admin aggiornato con istruzioni per registrare e usare le passkey

---

### v1.16.1 (10/06/2026)

**PWA/favicon — fix icona su iPhone**
- Aggiunta `favicon.ico` (16/32/48px), `favicon-32x32.png` e `favicon-16x16.png` generate da `icon-192x192.png`
- Rimosso `<link rel="apple-touch-icon">` duplicato senza `sizes` che sovrascriveva in Safari il tag corretto con `sizes="180x180"` emesso da django-pwa — l'icona installata su iPhone ora si aggiorna

---

### v1.16.0 (10/06/2026)

**PWA — splash screen e shortcuts**
- Splash screen dedicati per tutti i dispositivi iOS e iPad (iPhone SE → iPhone 16 Pro Max, tutte le iPad) — schermata di avvio personalizzata durante il caricamento dell'app
- Shortcuts nell'icona: dopo l'installazione, tasto lungo (Android) o pressione prolungata (iOS 13+) espone i collegamenti rapidi a **Diari**, **Valutazioni** e **Helpdesk**
- Icone aggiornate: set completo con nuove varianti 180×180 e 1024×1024

**Fix**
- Timeout sessione 4h e scadenza automatica alla chiusura del browser
- `_val()` normalizza float interi da openpyxl (es. numeri di telefono salvati con `.0` finale)
- Rinomina URL interno `allegati_delete` → `allegati_elimina`

---

### v1.15.0 (08/06/2026)

**Email — nome mittente**
- Nuovo campo "Nome mittente" in Impostazioni → Posta elettronica: le email vengono inviate come `Nome <email@dominio.it>`

**Cache PDF — interruzione generazione massiva**
- Pulsante "Interrompi" nella pagina Cache PDF: ferma ordinatamente il task Celery dopo il diario in corso (flag cooperativo via Redis); il log riporta "Interrotta" con conteggio parziale

**PWA — prompt di installazione**
- Icone app (192×192, 512×512, apple-touch-icon 180×180) generate dall'emblema AGESCI Campania
- Banner verde di installazione: su Android/Chrome gestisce `beforeinstallprompt`; su iOS Safari mostra istruzioni manuali (Share → Aggiungi a Home)

**UI mobile — fix footer**
- Aggiornamento `django-agesci-campania-theme` 1.1.0 → 1.2.4: layout viewport fisso limitato a ≥992px; su mobile il footer scorre con il contenuto

**Deploy**
- `collectstatic` va eseguito sull'host prima di `up -d` (il bind mount `./staticfiles` persiste tra i rebuild e sovrascrive i file statici baked nell'immagine)

---

### v1.13.0 (08/06/2026)

**Import Risposte EG — asincrono Celery**
- Nuovo task `task_import_risposte_eg`: elabora il file xlsx in background, manda email agli Admin all'avvio e al completamento con l'output completo
- Nuova card "4. Risposte EG" nella pagina Import con upload xlsx e selezione edizione

**Template PDF aggiornato**
- Dati generali: Capo Squadriglia con email e cell da Anagrafica.csq_* (se disponibili)
- Presentazione: colonna unica "Nome e cognome" (rimosso cognome separato)
- Imprese — Posti d'azione: tabella Chi / Cosa (con fallback su `descrizione` per dati pre-migrazione)
- Imprese — Specialità/brevetti: colonna Chi aggiunta
- Missione: rimossa sezione Posti d'azione

**Fix**
- Pulsante Dilazione nascosto quando `stato ≥ INVIATO` (CRP ha già inviato)
- Eliminazione foto disponibile anche dal dettaglio diario (card Imprese e Missione)
- Fix `timezone.utc` → `timezone.UTC` in `notifications/views.py` (Python 3.14 / Django 6 compat)

**Test suite: 117 → 138 (+21)**
- `TestModuliCsqCompleti`: 8 test per logica NUOVO/RINNOVO
- `TestEliminazioneAllegati`: 5 test per permessi eliminazione per stato e ruolo
- `TestDilazioneContext`: 4 test per context dilazione
- `TestNuoviCampiModello`: 4 test per PostoAzione.chi+cosa, EsitoSpecialita.chi, MembroSq.nome, Anagrafica.csq_*

---

### v1.12.0 (08/06/2026)

**Revisione completa UI Diario di Bordo (moduli 1–6)**

*Modulo 1 — Anagrafica*
- Aggiunti campi Capo Squadriglia (nome, cognome, email, cell) editabili
- Campo nome squadriglia editabile: rinomina anche le cartelle su Google Drive
- Selezione tipo partecipazione (Nuovo / Rinnovo) nella sezione Specialità
- Sezione "Note da import (precompilazione)" sempre in sola lettura
- Tooltip esplicativi su tutti i campi
- Abbreviazioni CRP/GV eliminate dall'UI → "Capo Reparto", "Guidoncini Verdi"

*Modulo 2 — Presentazione squadriglia*
- Membri: solo nome (rimosso il campo cognome separato)
- 3 righe iniziali preimpostate (Capo Squadriglia, Vice, Squadrigliere)
- Pulsante "Aggiungi membro" per inserire righe aggiuntive

*Moduli 3/4 — Imprese*
- Posti d'azione suddivisi in **Chi** e **Cosa** (migrazione automatica dei dati esistenti)
- Specialità individuali e brevetti di competenza: campo **Chi** per indicare il membro
- Pulsanti "Aggiungi riga" per posti d'azione, specialità e brevetti
- Anteprima foto con pulsante di eliminazione (disponibile fino all'invio del Capo Reparto)
- Tooltip con descrizioni dettagliate per Perché, Come, Cosa, Link esterno
- Pulizia automatica dei link Jotform presenti nei diari esistenti

*Modulo 5 — Missione*
- Rimossa sezione "Posti d'azione" (non prevista per la missione)
- Anteprima foto con pulsante di eliminazione
- Tooltip su "Descrizione svolgimento"

*Modulo 6 — Relazione finale (Capo Reparto)*
- Label "Specialità conquistata" → "Ritieni che la specialità di squadriglia sia stata conquistata?"
- Tooltip con descrizioni dettagliate per tutti i campi

**Dettaglio diario**
- Card Anagrafica: mostra dati CSQ, tipo partecipazione, precompilazione da import
- Card Presentazione: membri con solo nome
- Card Imprese: posti d'azione con Chi in grassetto, specialità/brevetti con Chi
- Card Missione: rimossa sezione posti d'azione

**Lista diari — filtri a cascata**
- I menu a tendina (Zona, Gruppo, Specialità, Stato, Tipo) si aggiornano in tempo reale
  mostrando solo le opzioni presenti nelle righe visibili dopo i filtri attivi

**PDF e Google Drive**
- Fix: `carica_pdf_diario` ora include sempre la Relazione finale (modulo 6)
- Drive: prima di caricare un PDF/Excel, l'eventuale versione precedente viene eliminata automaticamente — la cartella di output mantiene solo l'ultima versione

**Footer**
- Link "Manuale" spostato dalla navbar al footer come ultimo elemento fisso
- Link sociali: massimo 4 (era 5)

---

### v1.10.0 (07/06/2026)

**PDF diari**
- Il PDF include ora la **Relazione finale del Capo Reparto** (modulo 6)
- Accessibile solo a CRP, Incaricati EG e Admin (non al Capo Squadriglia)
- Compressione immagini nel PDF (480px) — riduzione dimensione ~80%
- Lock anti-duplicati: impossibile avviare due task paralleli per lo stesso diario
- Errori task: notifica all'utente richiedente e agli Admin con traceback; log in Impostazioni

**Allegati**
- Resize automatico al caricamento (default 1024px, configurabile in Impostazioni → Allegati)
- Conversione automatica in JPEG quality 85

**Impostazioni**
- Form per sezione con salvataggio indipendente (fix: la validazione email non bloccava più il salvataggio di altre sezioni)
- Nuova sezione **Sicurezza**: MFA + protezione brute-force (tentativi, cooloff, scadenza tentativi)
- Sblocco IP in Impostazioni (lista IP bloccati con sblocco singolo o massivo)
- Nuova sezione **Allegati**: dimensione massima immagini
- Fix Gmail OAuth2: i campi SMTP manuali vengono nascosti quando OAuth è attivo
- Tag template nel footer: `{{ titolo }}`, `{{ sottotitolo }}`, `{{ versione }}`, `{{ commit }}`
- Bottoni **Test SMTP** e **Test provider transazionale** con feedback errore inline
- Fix XOAUTH2 doppia codifica (errore Gmail 501 Cannot Decode)
- Fix formato data "Aggiornato il" (lettere a/l/e interpretate come codici Django)

**Monitoraggio**
- **Flower** (dashboard Celery): avviabile con `COMPOSE_PROFILES=flower docker compose up -d`; accessibile su `/celery/` per gli staff
- Comandi console per ispezione task: `celery inspect active`, `celery inspect stats`

**Deploy**
- Documentato il processo deploy corretto: `build --no-cache` + `up -d` (non `restart`)
- Gunicorn timeout 30s → 120s

---

## Licenza
[MIT](LICENSE) — Copyright © 2026 Andrea Bruno.
