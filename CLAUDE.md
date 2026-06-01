# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

Questo file orienta Claude Code nello sviluppo di **Plancia**. Leggilo prima di scrivere codice.

## Cos'è Plancia
Piattaforma per la gestione dei **Guidoncini Verdi** di AGESCI Campania (Branca E/G): le
squadriglie compilano un *Diario di Bordo*, i capi lo integrano, gli Incaricati EG lo valutano e
pubblicano l'esito. Edizioni annuali, generazione di PDF/Excel, upload su Google Drive, PWA con
resilienza offline.

## Fonte di verità
**`docs/Plancia_Progettazione.md`** è la specifica completa e autorevole: ruoli e permessi, modello
dati, moduli del Diario, macchina a stati, ciclo di vita dell'edizione, sicurezza, deployment.
In caso di dubbio, quel documento prevale su questo file. Se trovi ambiguità, segnalale invece di
inventare requisiti.

## Stack
- Python **≥ 3.14**, Django **≥ 6.0** (usa Background Tasks e CSP nativi dove utile).
- PostgreSQL **≥ 17**. Redis + **Celery** per i job asincroni.
- **uv** per dipendenze/venv. **Bootstrap 5** lato frontend. **WeasyPrint** (PDF), **openpyxl** (Excel).
- Auth: **django-allauth** (email + social Google/Microsoft/Apple, **MFA**, log sessioni).
  Permessi object-level con **django-guardian**, brute-force con **django-axes**.
- PWA con **django-pwa** + service worker/IndexedDB costruiti sopra.
- File su **Google Drive** via OAuth.

## Layout del repository
```
config/            # progetto Django (settings/base|dev|prod, urls, celery, wsgi, asgi)
apps/<app>/        # app di dominio (name="apps.<app>", label="<app>")
  accounts org editions diaries evaluations notifications storage_drive exports helpdesk stats
  siteconfig imports
deploy/            # Dockerfile-related, vhost template, configure-prod.sh, conf nginx, backup.sh
fixtures/          # CSV sintetici per provare gli import (NIENTE dati reali)
logs/              # log applicativi e log email simulati (logs/email/)
docs/              # specifica di progetto
.run/              # run configuration condivise PyCharm
```
- L'**utente custom** è già definito (`apps.accounts.models.User`, `AUTH_USER_MODEL="accounts.User"`):
  **estendilo**, non sostituirlo (AUTH_USER_MODEL non è modificabile dopo la prima migrazione).
- Le app sono scheletri vuoti con `TODO`: implementa modelli → migrazioni → admin → servizi → viste →
  template → test.

## Comandi principali

```bash
# Setup iniziale
uv sync
cp .env.dev.example .env.dev
docker compose -f docker-compose.dev.yml up -d db redis
uv run python manage.py makemigrations && uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000

# Test (DJANGO_SETTINGS_MODULE già impostato in pyproject.toml → config.settings.dev)
uv run pytest                                       # tutti i test
uv run pytest apps/accounts/                        # singola app
uv run pytest apps/accounts/tests.py::NomeTest      # singola classe/funzione

# Qualità del codice
uv run ruff check .                                 # lint
uv run ruff format .                                # format
uv run mypy .                                       # type check

# Pre-commit (prima volta)
uv run pre-commit install

# Worker Celery (non necessario in dev: CELERY_TASK_ALWAYS_EAGER=True)
uv run celery -A config worker -l info

# Alias mise (opzionale): install / up / down / migrate / dev / worker / lint / format / test
```

## Stato dell'implementazione

**UI**: usa `django-agesci-campania-theme` (installato). Template estendono `base.html` → `agesci_theme/base.html`. Setting: `AGESCI_THEME_BRANCA = "eg"`.

**CRITICO — navbar e blocchi del tema**: `{% block %}` nei template `{% include %}` **non** partecipano
all'ereditarietà Django. Il tema usa `{% include "agesci_theme/partials/navbar.html" %}`, quindi
`{% block brand_text %}` e `{% block nav_items %}` al suo interno sono opachi. Per personalizzare la
navbar, sovrascrivere **completamente** `{% block navbar %}` in `base.html` senza usare `{{ block.super }}`
per la parte delle voci. Vedi `templates/base.html` come riferimento.

App con modelli e UI completi:
- **`accounts`** — `User` (+ `socio` OneToOneField), `Nomina`, `LoginEvent`; `roles.py` (+ service `nomina()`); `signals.py` (+ `ensure_superuser_ruolo`: imposta automaticamente `ruolo=ADMIN` quando `is_superuser=True` viene salvato — corregge il default CSQ di `createsuperuser`); `mixins.py`; `forms.py` (Bootstrap mixin + form allauth); `views.py` (`ProfiloView`, `UtenteListView`, `UtenteDetailView`, `NominaView`); `urls.py` (namespace `accounts`, mountato su `utenti/`). Template: `accounts/profilo|utente_list|utente_detail`. Test: `apps/accounts/tests/`.
- **`org`** — `Zona`, `Gruppo`, `Reparto`, `Squadriglia`, `Socio`; autocomplete `GET /api/soci/?q=&categoria=` (login required).
- **`editions`** — `Edizione` (FSM 4 stati), `Dilazione`; CRUD views + template. Namespace `editions`.
  Campi evento: `data_evento_inizio`/`fine`, `evento_comune` (autocomplete comuni-ita), `evento_localita`.
  Drive: `drive_folder_allegati_id` (ex `foto`), `drive_folder_output_id`, `drive_oauth_account`.
  `HomeView` (root `/`): reindirizza all'edizione con stato `APERTA`/`IN_VALUTAZIONE` più recente per anno; se nessuna attiva mostra `templates/home_no_edizione.html`.
- **`diaries`** — `Diario` (FSM 7 stati), moduli 1–6, `Allegato`; views + template. Namespace `diaries`. Test FSM + visibilità: `apps/diaries/tests/`.
  Costanti ufficiali in cima a `models.py`: `SPECIALITA_SQUADRIGLIA` (12, Allegato 3), `SPECIALITA_INDIVIDUALI` (66, Allegato 2), `BREVETTI_COMPETENZA` (15, Allegato 4).
  `Anagrafica.specialita` usa queste choices. `MembroSq.ruolo` ha choices `RuoloSq` (csq/vcsq/squadrigliere/altro). `SentieroCammino` ha valori `scoperta/competenza/responsabilita/non_specificato`.
  `EsitoSpecialita` ha campo `tipo` (`TipoEsito.SPECIALITA` / `TipoEsito.BREVETTO`); i form impresa usano due formset separati (`SpecialitaFormSet` + `BrevettoFormSet`) con prefissi `specialita`/`brevetti`.
  `Anagrafica` **non ha più** `email_contatto` e `cell_contatto` (rimossi — migrazione `0004`).
- **`notifications`** — `MailTemplate`, `Invito` (token UUID), `render_mail()`; service + tasks Celery; views attivazione/reinvio. Namespace `notifications`. Template default in `templates/mail/`.
- **`evaluations`** — `Valutazione`, `AssegnazionePGV`; views per PGV/Incaricato (assegna, proponi, conferma, rigetta, pubblica). Namespace `evaluations`.
  **Nota modello**: `AssegnazionePGV` ha FK verso `Valutazione` (non verso `Diario`); `related_name="assegnazioni_pgv"` è su `Valutazione`. Usare `valutazione.assegnazioni_pgv` nelle query, non `diario.assegnazioni_pgv`.
- **`exports`** — PDF WeasyPrint (`genera_pdf_diario`), Excel openpyxl (`genera_excel_edizione`), tasks Celery con upload Drive opzionale. Template PDF: `templates/exports/diario.html`.
- **`storage_drive`** — `DriveCredenziali`, `DriveFile`; service `carica_file/pdf/excel`, `crea_cartella`; views OAuth (`DriveOAuthInitView`, `DriveOAuthCallbackView`) + AJAX folder picker (`DriveFolderListView`, `DriveCartellaCreaView`). Namespace `storage_drive`, mountato su `drive/`. Settings: `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI` da env. In dev: `OAUTHLIB_INSECURE_TRANSPORT=1` settato automaticamente nel callback.
- **`helpdesk`** — `Ticket`, `RispostaTicket`; views CRUD + rispondi/chiudi/prendi. Namespace `helpdesk`.
- **`stats`** — dashboard per zona (esiti, tempi, ticket); visibile a staff. Namespace `stats`.
- **`siteconfig`** — `Impostazioni` singleton, middleware manutenzione, backend email custom; `forms.py` (`ImpostazioniForm` con widget Bootstrap, `MailTemplateForm` con TinyMCE). Namespace `siteconfig`.
  Campi footer: `footer_testo`, `footer_link_label` (default `campania.agesci.it`), `footer_link_url` (default `https://campania.agesci.it`).
  Context processor `apps.siteconfig.context_processors.impostazioni` inietta `impostazioni` in ogni template: usare `{{ impostazioni.titolo }}` ecc. senza passarlo esplicitamente nelle viste.
  Pagina impostazioni suddivisa in sezioni (Identità, Footer, Posta elettronica, Stato, Import, Template email).
  **Gestione MailTemplate da UI**: `MailTemplateEditView` (GET/POST `/impostazioni/mail/<chiave>/`), `MailTemplateImportaView` (POST `/impostazioni/mail/<chiave>/importa/` — legge il file di default `templates/mail/<chiave>.html` e crea il record), `MailTemplateDeleteView` (POST `/impostazioni/mail/<chiave>/elimina/` — solo Admin, ripristina fallback su file). Template editor: `templates/siteconfig/mail_template_edit.html` (TinyMCE + sidebar tag copiabili).
  Partial: `siteconfig/_campo.html`, `siteconfig/_switch.html`.
- **`imports`** — `LogImportazione`, `RigaImportazione`; management commands `import_coca/ragazzi/squadriglie` (upsert idempotente, riconciliazione CRP); task Celery; view riconciliazione. Namespace `imports`.
- **`editions`** — management command `archivia_edizione --genera/--purga --conferma`.

**`Diario.pubblicato`** è una property (`pubblicato_at is not None`). Usare `pubblicato_at__isnull=False` nelle query e assegnare `pubblicato_at = timezone.now()` per pubblicare.

Migrazioni create per tutte le app con modelli. Dopo ogni cambio di modello: `uv run python manage.py makemigrations <app>`.

URL montati: `admin/`, `accounts/` (allauth), `utenti/` (accounts app — namespace `accounts`), `hijack/`, PWA, `edizioni/`, `diari/`, `valutazioni/`, `notifiche/`, `helpdesk/`, `impostazioni/`, `import/`, `stats/`, `api/soci/`, `drive/`.
`/` → `HomeView` (redirect edizione attiva o pagina "nessuna edizione"); `/__debug__/` (debug toolbar, solo `DEBUG=True`).

Template allauth in `templates/account/` (tutti estendono `base.html`): login, logout, verification_sent, email_confirm, password_reset e varianti, **signup**, **signup_closed**, **password_change**, **password_set**, **email**, **account_inactive**, **reauthenticate**. Form Bootstrap via `ACCOUNT_FORMS` in settings (`apps.accounts.forms`): `PlanciaLoginForm`, `PlanciaSignupForm`, `PlanciaResetPasswordForm`, `PlanciaChangePasswordForm`, `PlanciaSetPasswordForm`, `PlanciaAddEmailForm`.

Template MFA in `templates/mfa/`: `authenticate.html`, `index.html`, `reauthenticate.html`; `totp/activate_form.html`, `totp/deactivate_form.html`; `recovery_codes/index.html`, `recovery_codes/generate.html`.

**Navbar** (`templates/base.html`): role-aware con badge utente (cerchio con iniziale, dropdown Profilo/Email/Password/MFA/Esci). PGV vede "Diari assegnati" (filtrati via `AssegnazionePGV`). Banner hijack arancio quando si impersona un utente. Voci Gestione filtrate per ruolo.
Brand navbar mostra `{{ impostazioni.titolo }}` (fallback "Plancia") e, se valorizzato, `{{ impostazioni.sottotitolo }}` in un secondo rigo più piccolo — entrambi vengono dal context processor `siteconfig`.

**Settings aggiuntivi**: `LOGIN_REDIRECT_URL = "/"` (evita il 404 su `/accounts/profile/` post-login). In `dev.py`: `STORAGES` sovrascrive a `StaticFilesStorage` per evitare che i test falliscano per mancanza del manifest di `collectstatic`.

**Dev email**: Mailpit in `docker-compose.dev.yml` (SMTP `:1025`, UI `http://localhost:8025`). In `dev.py`: `ACCOUNT_EMAIL_VERIFICATION = "none"` (nessun blocco in sviluppo) + `EMAIL_HOST/PORT` puntano a Mailpit.

**Dev MFA**: `MFAEnforcementMiddleware` è disabilitato quando `DEBUG = True` (primo check nel middleware). `MFA_TOTP_INSECURE_BYPASS_CODE = "000000"` in `dev.py` per saltare la verifica TOTP nei test. In sviluppo nessuno è mai bloccato dalla MFA.

**Tutto implementato.** Non ci sono funzionalità critiche pendenti.

## Ordine di costruzione consigliato (dalla roadmap, §15 del doc)
1. **org + accounts**: gerarchia Zona/Gruppo/Reparto/Squadriglia; ruoli; MFA per ruoli privilegiati.
2. **editions**: Edizione, due scadenze, data evento, cartelle Drive, import anagrafiche, dilazioni.
3. **diaries**: moduli 1–6, editing collaborativo CSQ↔CRP fino alla scadenza, FSM fino a `INVIATO`,
   regole Nuovo/Rinnovo (moduli 4–5 facoltativi se Rinnovo, comunque visibili).
4. **notifications**: inviti email + token, reinvio batch (WhatsApp solo come adapter stub).
5. **evaluations**: assegnazione PGV, `IN_REVISIONE`/conferma, modifica decisioni fino a
   pubblicazione, riapertura, pubblicazione (tutti / per round di scadenza).
6. **exports + storage_drive**: PDF (WeasyPrint), Excel (openpyxl), Drive OAuth, job Celery.
7. **PWA/offline**: service worker, autosave IndexedDB, coda di sync, foto offline.
8. **helpdesk + stats**: ticket e statistiche di chiusura (per zona, tempi, difficoltà).

## Regole di dominio da non sbagliare
- **Visibilità**: la Relazione finale CRP e la Valutazione non sono **mai** visibili al CSQ; la
  valutazione non è visibile a CSQ/CRP **finché non è pubblicata**. Applica la protezione a tre
  livelli: UI, view, queryset/serializer.
- **Rinnovo**: moduli 4 e 5 non obbligatori ma compilabili (decide il CSQ). Obbligatori solo se Nuovo.
- **`IN_REVISIONE`** solo per *Approvata*/*Non approvata* proposte da un membro PGV (richiedono
  conferma Incaricato). *Maggiori informazioni* non passa di lì.
- Gli **Incaricati EG** possono modificare qualunque decisione **fino alla pubblicazione**.
- **Riapertura** per integrazioni solo se valutazione su 1ª scadenza e 2ª non ancora passata.
- **PGV** valuta solo i diari assegnati e **non può ri-delegare**.

## Sicurezza (requisito, non opzione)
La piattaforma tratta **dati e foto di minori**. Minimizza i dati raccolti; cifra in transito e a
riposo; MFA obbligatoria per Admin/Segreteria/Incaricati; audit trail su transizioni di stato e
valutazioni; permessi object-level rigorosi. Mai esporre esiti non pubblicati. Vedi §12 del doc.

## Convenzioni di codice
- **ruff** (lint + format) configurato in `pyproject.toml`; `pre-commit` disponibile.
- Type hints dove sensato; docstring brevi in italiano per le parti di dominio.
- Una migrazione coerente per ogni cambio di modello; non editare migrazioni già applicate.
- Test con **pytest + pytest-django**; copri almeno FSM, permessi e regole di visibilità.
- Niente segreti nel repo: tutto via `.env*` / variabili d'ambiente.

## Soci, import e selezioni (vedi §14 del doc)
- `apps.org.Socio` è già abbozzato: `codice_socio` (**numerico 4–8 cifre, univoco**), nome, cognome,
  gruppo, zona, email, `categoria` (`capo`/`ragazzo`). I ruoli si selezionano da qui: **capi** →
  tutti tranne CSQ; **ragazzi** → solo CSQ.
- **Email**: quella di un *capo* non è modificabile dal capo (solo Segreteria/Admin/IABR); quella di
  un *ragazzo* (CSQ) è aggiunta dall'import Evento ed è modificabile dal ragazzo.
- **Import** (già abbozzati come management command in `apps.imports`, da completare + esporre come
  task Celery e UI): `import_coca`, `import_ragazzi`, `import_evento`. Idempotenti (upsert per
  codice socio). L'Evento identifica il CRP per email/nome → **riconciliazione** verso `Socio(capo)`
  con report dei mancati match. Mappatura colonne in Appendice D del doc; prova con `fixtures/`.
- **Autocompletamento**: ovunque si selezioni un capo/ragazzo, usa l'endpoint
  `apps.org.views.soci_autocomplete` (ricerca per nome/cognome/zona/gruppo/codice socio) + widget
  lato client (es. Tom Select). Filtra per permessi/ambito.

## Impostazioni di piattaforma (solo Admin — §15)
- `apps.siteconfig.models.Impostazioni` è un **singleton** (pk=1): titolo, sottotitolo,
  `footer_testo`/`footer_link_label`/`footer_link_url` (footer personalizzabile),
  SMTP, `manutenzione`, `debug_toolbar`, `debug_diagnostico`, `email_mode`.
- **Email**: il backend `apps.siteconfig.email_backends.PlanciaEmailBackend` rispetta `email_mode`
  (`reale` / `simulato` → scrive in `logs/email/` / `simulato_piu_invio`). In dev resta il backend
  console.
- **Template email** (rich text): `apps.notifications.models.MailTemplate` + `TAG_REGISTRY` (tag
  ammessi per chiave). `render_mail(chiave, context)` applica **solo** i tag previsti. Editor WYSIWYG
  via **django-tinymce**. L'editor mostra i tag disponibili.
- **Template PDF**: `apps.exports.models.PdfTemplate` (HTML WeasyPrint) **scaricabile e caricabile**
  da Impostazioni; default su file `templates/exports/diario.html`. Nel PDF del CSQ **non** vanno
  Relazione finale né Valutazione.
- **Import dei tracciati**: avviabili dalla pagina Impostazioni da **Admin, IABR e Segreteria**.
- **Manutenzione**: `MaintenanceModeMiddleware` mostra una pagina di cortesia a tutti tranne admin.
- **DEBUG reale**: governato da `DJANGO_DEBUG` in `.env.prod` e **richiede redeploy/restart** (si
  legge all'avvio). `prod.py` fa `DEBUG = env.bool("DJANGO_DEBUG")`. **Non** ribaltare DEBUG a
  runtime: in pagina restano solo debug-toolbar (admin) e logging verboso.

## Ruoli: creazione e nomina (§2)
- Regole in `apps.accounts.roles` (`ROLE_REQUIRES_CATEGORY`, `ROLE_CREATABLE_BY`, `puo_nominare`,
  `categoria_compatibile`) + modello `apps.accounts.models.Nomina` (audit).
- Admin creato solo da Admin (+ `createsuperuser`); Segreteria da Admin; IABR da Admin/Segreteria.
- Segreteria e IABR **devono essere capi**; Admin può essere un account senza Socio.
- PGV/CRP solo a *capi*; CSQ solo a *ragazzi* (vincolo validato in fase di nomina).

## Impersonazione (§2)
- Solo **Admin** e **Segreteria** impersonano; solo verso utenti con **rango ≤ al proprio**
  (la Segreteria non impersona un Admin). Ranghi e logica in `apps.accounts.roles`
  (`ROLE_RANK`, `puo_impersonare`, `can_hijack`).
- Implementata con **django-hijack**: `HIJACK_PERMISSION_CHECK = "apps.accounts.roles.can_hijack"`,
  urls `hijack/`, banner di sessione. Logga ogni impersonazione (audit).

## Retention / archiviazione (§7, §12)
- Comando `archivia_edizione` (app `editions`) in due passi su edizioni **chiuse**:
  `--genera` (PDF dei diari + Excel esiti su Drive) e `--purga --conferma` (elimina le **foto** e
  marca l'edizione archiviata; i link esterni restano come testo). Idempotente; la cancellazione è
  loggata. Rifiuta se l'edizione non è chiusa o se gli output non sono su Drive.

## Import: riconciliazione (§14)
- `apps.imports.models.LogImportazione`/`RigaImportazione`: l'import Evento aggancia il CRP per
  **email**; le righe senza match vanno `da_riconciliare` e si correggono dalla **schermata di
  riconciliazione manuale** (accesso Admin/IABR/Segreteria) con autocompletamento Socio(capo).

## Backup
`deploy/backup.sh` (cron) fa `pg_dump` dal container + gzip, tar di media/log, retention e notifica.
Pianificazione in `deploy/crontab.example`. Non reintrodurre la stessa logica in Celery se non
richiesto.

## Cosa NON fare
- Non cambiare `AUTH_USER_MODEL` né l'app label dopo le prime migrazioni.
- Non rendere visibili valutazioni/relazioni oltre i ruoli previsti.
- Non introdurre storage browser non supportato negli artifact PWA (usa IndexedDB/SW come da §9).
- Non implementare WhatsApp finché non è una decisione presa (resta un adapter dietro `Notifier`).
- Non versionare né includere nei pacchetti i CSV reali (minori/dati sensibili): usa solo `fixtures/`.
- Non rendere il codice socio editabile a mano dove deve restare la chiave d'import; validalo come
  numerico 4–8 cifre.
