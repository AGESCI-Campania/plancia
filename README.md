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
django-guardian · django-axes · django-pwa · Bootstrap 5 · django-agesci-campania-theme 1.1.0 ·
django-bootstrap-icons · WeasyPrint · openpyxl · Google Drive (OAuth).
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
| **accounts** — ruoli e nomina | 19 | ✅ pass | Permessi, ranghi, puo_nominare |
| **diaries** — FSM | 16 | ✅ pass | Transizioni stato, riapertura |
| **diaries** — visibilità | 6 | ✅ pass | Accesso a moduli per ruolo |
| **diaries** — cambio referenti | 29 | ✅ pass | CambiaCsqView, CambiaCrpView, bulk |
| **diaries** — Selenium E2E | 12 | ✅ pass | Chrome headless, Tom Select, sessione |
| **Totale** | **112** | **✅ 112/112** | `uv run pytest` — 2026-06-04 |

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

## Impostazioni di piattaforma (solo Admin)
Pagina `/impostazioni/` riservata ad Admin, IABR e Segreteria, organizzata in sezioni:

| Sezione | Campi |
|---|---|
| **Identità** | Titolo · Sottotitolo (visualizzati nella navbar) |
| **Footer** | Testo rich text · Fino a 5 link tipizzati (Sito web, Email, Facebook, Instagram, TikTok) con etichetta opzionale |
| **Posta elettronica** | Modalità email · Provider (SMTP / Brevo / Mailgun / ecc.) · API key · Webhook secret · From · SMTP |
| **Stato e diagnostica** | Manutenzione · Debug toolbar · Debug diagnostico |
| **Import tracciati** | Avvia import Co.Ca. / Ragazzi / Evento + link storico |
| **Template email** | Elenco tutte le chiavi con stato (DB / file default) |

**Template email**: ogni chiave del registro può essere personalizzata in rich text (TinyMCE)
direttamente dalla pagina impostazioni. Se il template non è in DB usa il file di default
`templates/mail/<chiave>.html`; il pulsante **"Importa da file"** carica quel file come punto
di partenza per la personalizzazione. Il pulsante **"Elimina"** ripristina il fallback su file.

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
