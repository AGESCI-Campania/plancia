# Piano — Plancia 3.0: dipendenze aggiornate, PostgreSQL 18, SPA Vue + Bootstrap 6, una sola installazione

## Context

Plancia sarà installata da zero sul nuovo server `*.agescicampania.net` (predisposto nei commit
`947b9d8`, `f6910b4`), non prima di **gennaio 2027**, con **una sola installazione**. Si sfrutta
l'occasione per:
- portare **tutte** le dipendenze Python alla latest (anche major: Django 6.1, axes 9, redis-py 8,
  Pillow 13, gunicorn 27, WeasyPrint 70, …), PostgreSQL 17 → **18**, immagine base fissata
  (Ubuntu 26.04 e Docker sul server sono già aggiornati: nessun passo di sistema);
- sostituire tutta l'interfaccia Django (~75 template, ~90 viste) con una **SPA Vue** con Bootstrap 6
  (la "serie 3.x" del tema), **tutto in Vue**, login/MFA compresi (allauth headless).

Stack del frontend: Vue 3.5, TypeScript 6, Vite 8, vue-router 5, Pinia 4, Dexie 4,
vite-plugin-pwa 2, Bootstrap 6 alpha, Vitest 5, Playwright.

> Documento di lavoro del branch `v3`: **non va portato su `main`** al merge (a quel punto il
> piano sarà realizzato; resta nella history).

Lavoro su branch `v3` (lungo), merge su `main` e installazione solo a SPA completa e verificata.
Versione di rilascio: **3.0.0**.

## Decisioni prese (2026-11-16)

Domande chiuse prima di partire, per non fermare lo sviluppo fase per fase:

| # | Tema | Decisione |
|---|---|---|
| 1 | `aggiorna.sh` | **Su tag, come qdc**: ultimo `vX.Y.Z` (o quello indicato), novità dal changelog, manutenzione, backup, build, attesa `healthy`, **rollback automatico** (se il DB è già migrato: resta in manutenzione e indica il backup). Release: **prima** tag + GitHub Release, **poi** deploy |
| 2 | PWA ≠ server | **Modale rimandabile** ("È disponibile la versione X.Y.Z", Aggiorna / Più tardi), ripresentata a ogni avvio; prima sincronizza la coda offline (offline: avvisa e non aggiorna); badge con Aggiorna nel footer |
| 3 | Aggiornamento da Impostazioni | **Sì, schema completo** (§ Versioni e aggiornamenti) |
| 4 | Migrazioni | **Rigenerate da zero**: una `0001_initial` per app dopo le modifiche ai modelli; data migration utili → seed/fixture |
| 5 | Dati offline | **Nessuna cifratura**; cancellazione al logout e a sessione scaduta (con avviso se c'è coda), solo i diari dell'utente |
| 6 | Editor email/pagine | **Tiptap** (Vue, barra Bootstrap, segnaposto come pulsanti); via TinyMCE |
| 7 | `django-agesci-campania-theme` | **Rimosso**: pagine d'errore HTML statiche autonome (servite anche da nginx), callback → SPA |
| 8 | Ambiente di prova | **Docker sul Mac** (rete `agesci-proxy` finta); systemd/`.path` non verificabili in locale → runner provato a mano, unit verificate all'installazione sul server |
| 9 | Autonomia | Commit a ogni passo verde e **push su `origin/v3`**; stop solo per merge su `main`, tag/release, server/Sestante/Caddy, decisioni nuove |

Scelte di default conseguenti (non chieste): versione unica in `pyproject.toml`, letta da Vite
(`__VERSIONE_APP__`); changelog spostato da `README.md` a **`CHANGELOG.md`** (sezioni
`## X.Y.Z — AAAA-MM-GG`, letto da `aggiorna.sh` e dalla pagina di aggiornamento); tipi del client
generati da OpenAPI (`openapi-typescript`); autocomplete Socio come componente Vue (via Tom Select).

## Versioni e aggiornamenti (requisito aggiunto)

- **Versione server**: `GET /api/v1/sito` (pubblico) restituisce `versione`; `/app-status` invariato
  per l'app mobile. **Versione PWA**: `__VERSIONE_APP__` iniettata in build.
- **Footer**: due etichette, *App vX.Y.Z* (installata) e *Server vX.Y.Z*; se diverse, badge +
  pulsante Aggiorna (`aggiornaOra`: `registration.update()`, attesa del nuovo SW, `skipWaiting`, reload).
  Service worker in modalità *prompt* (`vite-plugin-pwa`), confronto semver come
  `versioneInferiore` di qdc; la versione server letta da cache non conta.
- **Modale** (decisione 2) in `AggiornamentoApp.vue`; non compare offline.
- **`scripts/aggiorna.sh`** riscritto sul modello qdc (`git checkout` del tag eseguendo una copia
  dello script, `sort -V`, novità da `CHANGELOG.md`, diff di `.env.template`, manutenzione via
  comando `manage.py manutenzione attiva|disattiva|stato`, backup, `docker compose build`/`up -d --wait`,
  rollback) mantenendo `_comune.sh`/`_plancia.sh`, `controlla_var_nuove`, unit systemd. Opzioni
  `--si` (non interattivo) e `--stato-file <path>` (avanzamento in JSON per la pagina web).
- **Aggiornamento dal web (solo Admin)**:
  - task Celery beat giornaliero: GitHub Releases API (`repos/<org>/plancia/releases/latest`, senza
    token o con token read-only da `.env`) → `Impostazioni.ultima_release_*` (versione, note, data);
  - pagina *Impostazioni → Aggiornamenti*: versione installata, disponibile, note; pulsante
    **Aggiorna a vX.Y.Z** con conferma e **riautenticazione MFA**; audit (chi, quando, esito);
  - Django scrive **solo** `aggiornamenti/richiesta.json` in una cartella bind-mount
    (`/opt/plancia/aggiornamenti`); **mai `docker.sock` nel container**;
  - host: `plancia-aggiorna.path` (utente `agesci`) → `plancia-aggiorna.service` che valida la
    richiesta (formato tag, tag esistente), la sposta in `in-corso.json` e lancia
    `scripts/aggiorna.sh --si vX.Y.Z --stato-file …`; log in `aggiornamenti/log/`; una sola
    esecuzione alla volta (lock); installate da `installa.sh` come le altre unit;
  - la pagina fa polling dello stato (API che legge il file) e regge il riavvio (manutenzione →
    ritorno `healthy` → reload); email all'Admin con esito e log; variabili `.env` mancanti → stop
    con messaggio mostrato nella pagina.
- **Fasi**: endpoint versione + comando `manutenzione` in Fase 2; footer/modale/SW in Fase 3;
  pagina Aggiornamenti in Fase 4; `aggiorna.sh`, runner e unit in Fase 6; CLAUDE.md § Release
  aggiornato (tag prima del deploy).

## Architettura di arrivo

```
Caddy ──► plancia-nginx:80 ──┬─ /                → SPA (frontend/dist, file statici + fallback index.html)
                             ├─ /api/v1/          → web:8000 (django-ninja)
                             ├─ /_allauth/        → web:8000 (allauth headless: browser + app)
                             ├─ /accounts/oidc/…  → web:8000 (solo callback dei provider social/SSO)
                             ├─ /admin/, /static/ → web:8000 (Django admin, WhiteNoise)
                             └─ /drive/…/callback, /impostazioni/gmail-smtp/…/callback,
                                /anymail/webhook/, /mailadmin/, /celery/, /healthz/ → web:8000
```
- **Backend** API-only: restano in Django solo email, PDF WeasyPrint, Django admin, callback OAuth
  (Drive, Gmail SMTP, provider social/SSO) che poi reindirizzano alla SPA, webhook Anymail, proxy
  Mailpit/Flower (solo Admin), pagine d'errore minime (403/404/500/CSRF, servite anche da nginx).
- **Logica di dominio invariata e riusata**: `apps/evaluations/actions.py` (FSM/valutazioni),
  `apps/diaries/visibility.py::diari_visibili`, `apps/api/permissions.py`, `apps/accounts/roles.py`,
  servizi `apps/exports/service.py`, `apps/storage_drive/service.py`, import `apps/imports/`.
  Le viste Django spariscono, le regole no.
- **Auth**: SPA con client allauth headless *browser* (cookie di sessione same-origin + `X-CSRFToken`);
  l'app mobile continua con `X-Session-Token` (app-mode) e `/api/v1` invariato.
- **Tema**: la SPA usa Bootstrap 6 direttamente con la palette AGESCI presa dal tema **3.0.0aX**
  (SCSS copiato in `frontend/src/theme/`, branca EG). Il pacchetto `django-agesci-campania-theme`
  si rimuove (decisione 7).

---

## Fase 1 — Dipendenze, immagine, PostgreSQL 18 (backend attuale)

Prima di toccare l'interfaccia, così gli aggiornamenti sono verificati dai test esistenti.

| Pacchetto | Da → a | Azioni |
|---|---|---|
| Django | 6.0.5 → **6.1.x** | `django>=6.1,<6.2`; nessun uso delle API rimosse (verificato); attenzione a `first()/last()` dopo `order_by()`, Bcc negli header email; `EMAIL_*` deprecati → migrare a **`MAILERS`** insieme al dual backend (`apps/notifications/email_backends.py`, `get_connection_per_tipo`) |
| django-allauth | 65.18 → 65.22+ | riautenticazione cambiata (65.20–65.22), WebAuthn con user verification; ricontrollare `PlanciaAuthenticateView` e il bypass MFA SSO (`apps/accounts/adapters.py`) |
| django-axes | 8.3 → **9.0** | `migrate`; `AXES_CLIENT_IP_CALLABLE` invariato |
| redis-py | 6.4 → **8.1** | default RESP3: verificare Celery/kombu 5.7 e `RedisCache`; `protocol=2` se serve |
| celery / flower | 5.7 / 2.2 | nessuna rottura dichiarata |
| Pillow | 12 → **13** | `_resize_immagine` (`apps/diaries/views.py`, da spostare in un service), `_compress_image_for_pdf` |
| WeasyPrint | 68 → **70** | nessun uso di `url_fetcher`/`srgb`; Pango ≥ 1.44 |
| gunicorn | 26 → **27** | leggere il changelog da GitHub releases prima del bump |
| django-ninja | 1.6 → **1.8** | `Status(...)` per i codici; ordine campi ModelSchema; rivalidare OpenAPI |
| altri (guardian, environ, hijack, anymail, cors-headers, google-*, psycopg, uvicorn, …) | minor | changelog al bump |
| dev: ruff 0.17, mypy 2.4, django-stubs 6.1, pytest 9.2, pytest-django, debug-toolbar 8 | | |

- `selenium`/`webdriver-manager` da `dependencies` al gruppo `dev`.
- `Dockerfile`: `python:3.14.<patch>-slim-trixie`, uv all'ultima release.
- `docker-compose.yml` (e `.dev.yml`): `postgres:18`, volume montato su **`/var/lib/postgresql`**
  (con la 18 `PGDATA=/var/lib/postgresql/18/docker`); ricontrollare tag nginx/redis/mailpit.
- `.readthedocs.yaml` → Python 3.14; `.github/workflows/release-manual.yml`: verificare le major attuali
  di `actions/checkout` e `softprops/action-gh-release` (`gh api repos/<o>/<r>/tags`, `runs.using`).
- Verifica: `pytest`, `ruff`, `mypy`, ciclo `installa.sh`/`aggiorna.sh`/`backup.sh` in ambiente isolato.

## Fase 2 — API completa (django-ninja)

Oggi ~21 endpoint (`apps/api/routers/{system,me,editions,org,diaries,evaluations}.py`). Si porta in API
**ogni** funzione delle viste attuali, un router per dominio, schemi in `apps/api/schemas/`:

| Router | Da coprire (viste attuali) |
|---|---|
| `me` / `auth` | profilo, cambio ruolo attivo (`CambiaRuoloView`), sessioni, impersonazione (hijack acquire/release via API, stesse regole `can_hijack`) |
| `utenti` | lista/dettaglio utenti, crea staff (`nomina_staff_diretto`), nomine (`roles.nomina`) |
| `edizioni` | CRUD, FSM edizione, dilazioni, cartelle Drive (picker), Excel esiti, export diari (sync/async), archiviazione |
| `diari` | lista (`diari_visibili`), dettaglio, moduli 1–6 (anche gli endpoint PWA esistenti `apps/diaries/api_views.py`, da unificare), allegati/foto con resize, PDF (lock Redis, stato generazione, download), cambio referenti |
| `valutazioni` | già in parte; completare assegnazione PGV, proposte, pubblicazione (tutto via `actions.py`) |
| `notifiche` | inviti (singoli/bulk, CRP/CSQ), conferma codice socio, attivazione account, delivery status, template email |
| `impostazioni` | `Impostazioni`, footer, pagine statiche, SMTP/Gmail OAuth, cache PDF e progresso task, log export, manutenzione, axes |
| `import` | upload e lancio import, log/righe |
| `helpdesk`, `stats`, `org` (Socio autocomplete già c'è), `sito` (titolo/footer pubblici, anche prima del login) |

Regole: permessi solo backend (`permissions.py`, `actions.py`, `visibility.py`), mai duplicati; ogni
endpoint con test per ruolo (CSQ, CRP, PGV, Incaricato, Segreteria, Admin, estraneo) riprendendo
i test delle viste esistenti; visibilità relazione/valutazione invariata (§ Regole di dominio).

## Fase 3 — Frontend: impianto

- `frontend/` con Vite 8 + Vue 3.5 + TypeScript 6 + vue-router 5 + Pinia 4 + Dexie 4 +
  vite-plugin-pwa 2 + Bootstrap 6 alpha + bootstrap-icons + Vitest + Playwright, ESLint/Prettier
  (versioni verificate alla latest al momento, pin esatto di Bootstrap 6).
- `src/api/http.ts` (fetch, CSRF, errori tipizzati), `src/api/allauth.ts` (client headless browser),
  `src/api/plancia.ts` (tipi dagli schemi ninja; valutare generazione da OpenAPI).
- Auth completa in headless: login password, **SSO Sestante** e social (provider redirect
  `/_allauth/browser/v1/auth/provider/redirect`), TOTP, passkey/WebAuthn, codici di recupero,
  reset password, conferma email, attivazione CSQ con codice socio. Backend: `HEADLESS_ONLY = True`,
  `HEADLESS_FRONTEND_URLS`; **verificare che la callback OIDC resti
  `/accounts/oidc/sestante/login/callback/`** (altrimenti va aggiornato il blueprint su Sestante) e che
  il bypass MFA per sessioni Sestante funzioni anche in headless.
- Layout: menu laterale + drawer `<dialog>` su mobile, selettore ruolo, avatar per ruolo, breadcrumb,
  footer e titolo da `Impostazioni`, banner manutenzione, indicatori offline/sync.
- Store sessione (profilo, ruoli, flag menu); guardie router solo per l'interfaccia.
- **Nuova icona della PWA (scelta): "Diario di bordo".** Quadrato a angoli arrotondati verde E/G
  `#3D8E33`; quaderno bianco con dorso verde trasparente e tre righe verdi; segnalibro a guidoncino in
  giallo oro `#FFCC1E` in alto a destra. Dai **180 px in su** (icona Home, `apple-touch-icon`, 512 px,
  splash) in copertina, a sinistra del segnalibro, l'**emblema di AGESCI Campania a colori**
  (`agesci_theme/img/emblemi/EMBLEMA_CAMPANIA.png` del tema, ~20% del lato, a 35,5%/21% da
  sinistra/alto); sotto i 180 px (64, 48, 32 px, favicon) solo il quaderno. Da produrre: master SVG,
  PNG 32/64/180/192/512, variante *maskable* Android con l'area di sicurezza, `theme_color` = verde E/G,
  favicon. **Sorgenti approvati: `docs/icona-pwa/`** (generare le icone da lì, non ridisegnarle).

## Fase 4 — Pagine, per dominio

Home/edizione attiva, diari (lista con filtri, dettaglio, 6 moduli con autosave, allegati/foto, viewer
PDF con `navigator.share` su iOS), valutazioni, edizioni, utenti/nomine, inviti, impostazioni,
import, helpdesk, statistiche, profilo e sicurezza. Nessuna abbreviazione CSQ/CRP/PGV nell'UI
(regola esistente). Test Vitest per componenti/composables, Playwright per i flussi principali.

## Fase 5 — Offline (parità con l'attuale)

Riportare in Dexie + coda di invio (outbox con idempotenza) le funzioni oggi in
`static/js/plancia-{idb,autosave,moduli-offline,sync,foto,sw}.js`: moduli compilabili offline, coda
foto, sync alla riconnessione, banner "modifiche in attesa", shell PWA in cache, mai risposte API
nel service worker. Dati sul dispositivo non cifrati, cancellati al logout/scadenza
sessione (decisione 5).

## Fase 6 — Pulizia backend e deploy

- Rimuovere viste/URL/template Django non più usati, `static/js/*`, Tom Select, TinyMCE (se l'editor
  dei template email passa a un editor Vue), `django-pwa`; tenere email, PDF, admin, callback, errori.
- `frontend/Dockerfile` multi-stage (build Node → nginx con `dist/` e la conf attuale
  `deploy/nginx/default.conf.template` estesa con il routing sopra; resolver dinamico invariato).
  Il servizio `nginx` del compose diventa un'immagine costruita (`plancia-nginx:locale`).
- `scripts/installa.sh`/`aggiorna.sh`: build anche dell'immagine frontend; healthcheck nginx anche
  su `index.html`. Contratti frontend/Sestante invariati (stesso alias, nessuna porta).
- CSP di produzione (`config/settings/prod.py`) adeguata alla SPA; CORS solo per l'app mobile.
- Documentazione: CLAUDE.md (nuova architettura, comandi frontend), README e changelog 3.0.0, guida
  SSO, manuali con screenshot rigenerati via Playwright, guida privata `note/installazione-server.md`.

## Verifica finale

- Backend: `uv run pytest`, `ruff`, `mypy`; frontend: `vue-tsc`, ESLint, Vitest, Playwright.
- Ciclo completo nell'ambiente isolato (installa → aggiorna → backup → ripristino) con sonda via
  `agesci-proxy`: SPA, deep link (fallback `index.html`), API, admin, callback OAuth, healthz.
- Prova manuale dei flussi per ogni ruolo, PWA su iPhone (iOS ≥ 18) e Android, offline/riconnessione,
  generazione PDF ed export.
- Dopo l'installazione sul server: prova SSO end-to-end (guida privata § 9).

## Rischi

- Ambito ampio (riscrittura completa dell'interfaccia) per gennaio: Fasi 1–2 subito, ordine delle
  pagine per priorità d'uso (diari e moduli CSQ prima).
- Bootstrap 6 in alpha: pin esatto, aggiornamenti deliberati. Browser minimi Safari/iOS 18, Chrome 130.
- SSO in headless: callback e bypass MFA da riverificare; blueprint Sestante da aggiornare solo se la
  callback cambia (lo gestisce l'utente).
- App mobile: `/api/v1` resta compatibile (nessuna rottura degli endpoint esistenti senza versione).
