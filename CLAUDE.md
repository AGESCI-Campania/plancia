# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

Questo file orienta Claude Code nello sviluppo di **Plancia**. Leggilo prima di scrivere codice.

## Cos'è Plancia
Piattaforma per la gestione dei **Guidoncini Verdi** di AGESCI Campania (Branca E/G): le
squadriglie compilano un *Diario di Bordo*, i capi lo integrano, gli Incaricati EG lo valutano e
pubblicano l'esito. Edizioni annuali, generazione di PDF/Excel, upload su Google Drive, PWA offline.

## Fonte di verità
**`docs/Plancia_Progettazione.md`** è la specifica completa e autorevole. In caso di dubbio, quel
documento prevale su questo file.

## Stack
- Python **≥ 3.14**, Django **≥ 6.0**. PostgreSQL **≥ 17**. Redis + **Celery** per job asincroni.
- **uv** per dipendenze/venv. **Bootstrap 5** via **`django-agesci-campania-theme` 2.2.1**.
  Icone SVG inline con **`django-bootstrap-icons`**. **WeasyPrint** (PDF), **openpyxl** (Excel).
- Auth: **django-allauth** (email + social Google/Microsoft/Apple, **MFA**), **django-guardian**
  (object-level), **django-axes** (brute-force).
- Social login (guida: `docs/guide/social_auth.md`). Drive OAuth (guida: `docs/guide/google_drive_oauth.md`).
  **Apple Sign In**: `key`=TEAM_ID, `secret`=KEY_ID — la versione precedente aveva i campi scambiati
  causando 401 al callback; non invertire.

## Layout
```
config/         # settings/base|dev|prod, urls, celery
apps/           # accounts org editions diaries evaluations notifications
                # storage_drive exports helpdesk stats siteconfig imports
deploy/         # Dockerfile, nginx, entrypoint.sh, backup.sh
fixtures/       # CSV sintetici (NIENTE dati reali)
docs/           # specifica di progetto
```
`AUTH_USER_MODEL = "accounts.User"` — non modificabile dopo la prima migrazione.

## Comandi
```bash
uv sync && cp .env.dev.example .env.dev
docker compose -f docker-compose.dev.yml up -d db redis
uv run python manage.py migrate && uv run python manage.py runserver 0.0.0.0:8000
uv run pytest                         # tutti i test
uv run ruff check . && ruff format .  # lint + format
uv run mypy .
```

## App — modelli chiave
| App | Modelli |
|---|---|
| `accounts` | `User`, `Nomina`, `LoginEvent` |
| `org` | `Zona`, `Gruppo`, `Reparto`, `Squadriglia`, `Socio` |
| `editions` | `Edizione` (FSM 4 stati), `Dilazione` |
| `diaries` | `Diario` (FSM 8 stati), moduli 1–6, `Allegato` |
| `notifications` | `MailTemplate`, `Invito`, `TipoInvito`, `DeliveryStatus` |
| `evaluations` | `Valutazione`, `AssegnazionePGV` |
| `exports` | PDF WeasyPrint + Excel openpyxl, tasks Celery |
| `storage_drive` | `DriveCredenziali`, `DriveFile`, service `carica_file/crea_cartella` |
| `siteconfig` | `Impostazioni` (singleton), `FooterLink`, `GmailSMTPCredenziali`, `PaginaStatica` |
| `imports` | `LogImportazione`, `RigaImportazione`, commands `import_coca/ragazzi/squadriglie/risposte_eg` |
| `helpdesk` | `Ticket`, `RispostaTicket` |
| `stats` | dashboard per zona |

Autocomplete Socio: `GET /api/soci/?q=&categoria=` (Tom Select 2). URL montati in `config/urls.py`.
Context processor `impostazioni` inietta `Impostazioni` (singleton) in ogni template — usare
`{{ impostazioni.titolo }}` senza passarlo esplicitamente nelle viste.

## Gotchas e trappole

### Template e UI — Architettura layout (v2-offline)

**Schema di ereditarietà:**
```
agesci_theme/base.html             ← tema 2.2.1 (ag-scroll-area, header inlinizzato in base.html)
  └── templates/base.html          ← base Plancia: sidebar, header, footer, CSS
        └── templates/base_gestione.html  ← wrapper minimo per pagine staff
```

**Struttura layout (tema 2.2.0)**: nessun override di `agesci_theme/base.html` — il tema gestisce
già tutto correttamente. `.ag-scroll-area` è l'unico container con `overflow-y: auto` (su ≥992px);
`<main>` e `{% block footer %}` sono fratelli al suo interno. NON rimettere `overflow-y` su `<main>`.

**`templates/base.html`**:
- **Sidebar su tutte le pagine** (`{% block sidebar %}` con `ag-sidebar--dark`): voci di nav
  (Home, Diari, Helpdesk; Gestione/Sistema per staff). Su mobile nascosta via CSS (`d-none`
  sotto 992px) — la nav mobile è nell'offcanvas (hamburger in header).
- **Dropdown utente in sidebar** (`{% block sidebar_user %}`): sezione `ag-sidebar__user` in
  fondo alla sidebar con avatar colorato per ruolo, switcher multi-ruolo, link profilo/email/
  password/MFA e logout. Usa `dropup`. NON è nell'header.
- **Badge offline in `ag-header-top`**: `offline-indicator`, `photos-pending-badge`,
  `offline-sync-badge` sono nel wrapper `ms-auto` della barra superiore (prima dell'hamburger),
  visibili anche quando la breadcrumb occupa `ag-header-bottom`.
- **Breadcrumb**: `ag-header-bottom` mostra `{% include "agesci_theme/partials/breadcrumb.html" %}`
  se `breadcrumb_items` è nel contesto, altrimenti `header_search`/`header_actions` (vuoti).
  `header_actions` è libero per override dai template figli.
- **`header_nav`** è vuoto — non inserire voci lì, usare `{% block sidebar_items %}`.
- Blocchi **header**, **sidebar**, **footer** e relativi sub-blocchi sono **tutti inlinizzati**
  in `base.html` (HTML diretto, non `{% include %}`). **Motivo**: i blocchi Django dentro
  `{% include %}` non partecipano all'ereditarietà — sarebbero sempre vuoti.
- Per aggiungere voci alla sidebar: sovrascrivere `{% block sidebar_items %}` nel template
  figlio (il blocco è nella catena di ereditarietà, non in un include).

**Breadcrumb nelle view**: aggiungere `ctx["breadcrumb_items"]` in `get_context_data()`.
Formato: lista di dict `{"label": "...", "url": "..."}` — l'ultimo elemento ha `url: None`
(voce attiva senza link). Esempio:
```python
ctx["breadcrumb_items"] = [
    {"label": "Home", "url": "/"},
    {"label": "Diari", "url": reverse("diaries:list")},
    {"label": str(diario.squadriglia), "url": None},
]
```
View già aggiornate: `EdizioneDetailView`, `EdizioneListView`, `HomeView`, `DiarioListView`,
`DiarioDetailView`, `ProfiloView`, `UtenteListView`, `TicketListView`.

**`templates/base_gestione.html`**: solo `{% extends "base.html" %}`. La sidebar mostrata
è quella di `base.html` (che include già tutte le voci gestione per staff/admin).

- **Tema v2 — blocchi header**: `brand_url`, `brand_text`, `header_actions`, `offcanvas_nav`
  esistono e funzionano. `header_nav` è vuoto per scelta (nav in sidebar). Non sovrascrivere
  `{% block header %}` salvo casi eccezionali.
- **Tema v2 — footer**: blocchi `footer_brand_text`, `footer_col1_title`, `footer_col1_links`,
  `footer_col2_title`, `footer_col2_links`, `footer_text`, `footer_copyright`, `footer_links`
  funzionano perché inlinizzati in `base.html`. Non usare `class="footer-agesci mt-auto"`.
- **Componenti opzionali**: `{% load agesci_components %}` — tag disponibili: `ag_hero`,
  `ag_feature_card`, `ag_feature_grid`, `ag_jumbotron`, `ag_badge`, `ag_button`, `ag_breadcrumb`,
  `ag_dropdown`, `ag_list_group`, `ag_modal_trigger`, `ag_masonry_grid`.
- **Messages**: il tema gestisce `{% block messages %}` globalmente — **non aggiungere**
  `{% if messages %}` nei template, causerebbe duplicati.
- **Icone**: `{% load bootstrap_icons %}` + `{% bs_icon "nome" %}`. Mai `<i class="bi bi-*">`.
- **Abbreviazioni nell'UI**: CSQ/CRP/PGV non devono apparire nell'interfaccia. Usare "Capo
  Squadriglia", "Capo Reparto", "Pattuglia GV". Le abbreviazioni restano solo nel codice.

### Modelli e ORM
- **`Diario.pubblicato`** è una property (`pubblicato_at is not None`). Nelle query:
  `pubblicato_at__isnull=False`; per pubblicare: `pubblicato_at = timezone.now()`.
- **`AssegnazionePGV`** ha FK verso `Valutazione` (non `Diario`); `related_name="assegnazioni_pgv"`
  è su `Valutazione` — usare `valutazione.assegnazioni_pgv`.
- **`select_related("utente")`** (non `"user"`) nel queryset Socio: il reverse accessor è `utente`.
- **`Anagrafica`**: ha `crp_*` e `csq_*` (nome, cognome, email, cell). Non ha `email_contatto` né
  `cell_contatto` (rimossi — migrazione `0004`). `tipo_diario` non è un campo di Anagrafica: sta
  su `Diario.tipo`; in `AnagraficaForm` è gestito come campo extra non-model, salvato nella view.
- **`PostoAzione`**: i campi attivi sono `chi` (max 200) e `cosa` (max 300). Il vecchio campo
  `descrizione` esiste ancora per compatibilità (blank=True) ma non è più usato nell'UI né
  nell'import. La migrazione `0009` ha già diviso i dati esistenti.
- **`EsitoSpecialita`**: ha il campo `chi` (max 120, blank=True) per indicare il membro della
  squadriglia a cui è associata la specialità o il brevetto.
- **`MembroSq`**: `cognome` è blank=True/default="" — l'UI usa solo `nome` (campo unico "Nome e
  cognome"). L'ordinamento è su `["nome"]`. Non usare `cognome` in nuove funzionalità.
- **`Diario.moduli_csq_completi`**: per NUOVO richiede impresa1 + impresa2 + missione; per
  RINNOVO richiede solo impresa1 (impresa2 e missione sono facoltative).
- **`Socio.provvisorio`**: CRP creati automaticamente da `import_squadriglie` quando l'email non
  corrisponde; codice socio `tmpNNNNN`. Vengono sostituiti dalla riconciliazione import.

### Auth e ruoli
- **`{% hijack_button %}`** non esiste. Costruire manualmente:
  `<form method="post" action="{% url 'hijack:acquire' %}"><input type="hidden" name="user_pk" value="{{ utente.pk }}">`.
  `{% load hijack %}` fornisce solo `|can_hijack`; deve stare fuori da blocchi `{% if %}`.
- **Impersonazione**: usa il *rango massimo* tra tutti i ruoli attivi del target. La Segreteria non
  può impersonare chi ha nomina Admin.
- **`create_superuser`** crea con `ruolo=csq`; il signal `ensure_superuser_ruolo` corregge a DB
  ma l'oggetto in memoria resta vecchio — fare sempre `admin.refresh_from_db()` nei test.
- **Attivazione CSQ** (`TipoInvito.CODICE_SOCIO`): richiede conferma codice socio AGESCI + email.
  `_attiva_e_login` crea automaticamente `Nomina` se mancante (es. utenti con ruolo diverso preesistente).
- **`crea_o_ottieni_utente_per_socio`**: per CSQ senza email usa placeholder
  `noemail.{codice_socio}@noemail.internal`.

### FSM Diario (9 stati)
`non_iniziato` → `in_compilazione` → `relazione_finale` → `inviato` → `in_valutazione` →
`in_revisione`/`approvato`/`non_approvato`/`maggiori_info` → `in_compilazione`.
- Default creazione: `NON_INIZIATO`. Auto-transita a `IN_COMPILAZIONE` al primo salvataggio
  di un modulo CSQ (`_inizia_se_necessario` nei POST dei moduli e upload allegati).
- Moduli 1–5: editabili in `NON_INIZIATO` e `IN_COMPILAZIONE` (Capo Squadriglia).
- Modulo 6: solo in `RELAZIONE_FINALE` (Capo Reparto).
- **Non** usare `moduli_csq_completi` come guardia — usare `stato == RELAZIONE_FINALE`.
- Cambio referenti: `_STATI_PRIMA_INVIO = (NON_INIZIATO, IN_COMPILAZIONE, RELAZIONE_FINALE)`.
- **Flusso valutazione**: `ValutaDirettamenteView` accetta anche `INVIATO` e chiama
  `diario.avvia_valutazione()` automaticamente — non serve più che l'edizione transiti prima.
  Se c'è una proposta PGV `IN_REVISIONE`, l'Incaricato può comunque sovrascriverla con
  `valuta_direttamente()`. Test in `apps/evaluations/tests/test_flussi.py`.

### Drive e OAuth
- **PKCE obbligatorio** (da ottobre 2024): `DriveOAuthInitView` genera `code_verifier/challenge`,
  li salva in sessione; `DriveOAuthCallbackView` li passa a `fetch_token(code_verifier=...)`.
  Stesso pattern per `GmailSMTPOAuth*View`.
- **`Edizione.cartelle_configurate`** blocca **irreversibilmente** `drive_folder_allegati_id`,
  `drive_folder_output_id` e `cartella_diario_format` una volta valorizzati tutti e tre.
- **`carica_pdf_diario`** (in `storage_drive/service.py`): chiama sempre
  `genera_pdf_diario(diario, include_relazione=True)` e, prima di caricare il nuovo file,
  elimina il `DriveFile` precedente da Drive (un solo PDF per diario nella cartella di output).
- **Rinomina cartelle**: `AnagraficaUpdateView._rinomina_squadriglia` usa
  `service.files().update(fileId=folder_id, body={"name": nuovo_nome})` per rinominare le
  cartelle Drive quando si cambia il nome della squadriglia dall'anagrafica.

### Compatibilità Python 3.14 / Django 6
- **`timezone.utc`** non esiste più: usare `datetime.timezone.utc` oppure `timezone.UTC` (il modulo
  `django.utils.timezone` espone `UTC` come alias). Nei view che costruiscono epoch sentinel usare
  `timezone.datetime.min.replace(tzinfo=timezone.UTC)`.

### Email
- **Dual backend**: `email_backend_standard` (sistema/inviti singoli) vs `email_backend_massivo`
  (inviti bulk). `get_connection_per_tipo(tipo)` in `email_backends.py`. `email_mode` sovrascrive tutto.
- **Anymail signals** in `notifications/webhooks.py`, registrati in `NotificationsConfig.ready()`.
  Webhook: `/anymail/webhook/`.
- **Dev**: Mailpit su `localhost:8025`. `ACCOUNT_EMAIL_VERIFICATION = "none"` in `dev.py`.
- **Dev MFA**: middleware disabilitato quando `DEBUG=True`. Bypass TOTP: `000000`.
- **Passkey (WebAuthn)**: `allauth.mfa.webauthn` in `INSTALLED_APPS`, `MFA_SUPPORTED_TYPES=["totp","recovery_codes","webauthn"]` (obbligatorio — senza questa impostazione `webauthn` non compare in `SUPPORTED_TYPES`), `MFA_PASSKEY_LOGIN_ENABLED=True`, `MFA_PASSKEY_SIGNUP_ENABLED=False`. Usa `fido2` già incluso nell'extra `mfa` di allauth — nessuna dipendenza aggiuntiva. Nessuna migrazione necessaria (stessa tabella `allauth_mfa_authenticator`).
- **PlanciaAuthenticateView**: sovrascrive `mfa_authenticate` URL (`config/urls.py`) per evitare `begin_authentication()` su utenti senza passkey — il write inutile in sessione causava CSRF error su iOS Safari dopo redirect OAuth. Il bottone passkey nella login page richiede `form="mfa_login"` (attributo HTML di associazione al form nascosto, usato da `webauthn.js` via `loginBtn.form`).
- **MFA selettiva**: `Impostazioni.mfa_obbligatoria_ruoli_estesi` (default True). Se False, MFA obbligatoria solo per Admin; Segreteria e Incaricati EG possono accedere senza. `ruolo_richiede_mfa()` in `adapters.py` legge questa impostazione.

## Regole di dominio
- **Visibilità**: Relazione finale e Valutazione mai visibili al Capo Squadriglia; Valutazione non
  visibile finché non pubblicata. Protezione a tre livelli: UI, view, queryset.
- **Rinnovo**: modulo 4 (2ª impresa) e modulo 5 (missione) facoltativi; obbligatori solo se Nuovo.
- **`IN_REVISIONE`** solo per Approvata/Non approvata proposte da Pattuglia GV (richiedono conferma
  Incaricato). *Maggiori informazioni* non passa da `IN_REVISIONE`.
- **Incaricati EG**: modificano qualunque decisione fino alla pubblicazione.
- **Riapertura**: solo se valutazione su 1ª scadenza e 2ª non ancora passata.
- **Pattuglia GV**: valuta solo i diari assegnati; non può ri-delegare.

## Sicurezza
Dati e foto di minori: MFA obbligatoria per Admin/Segreteria/Incaricati; permessi object-level;
audit trail su transizioni stato e valutazioni; mai esporre esiti non pubblicati. Vedi §12 del doc.

## Ruoli e nomina
In `apps.accounts.roles`: `ROLE_REQUIRES_CATEGORY`, `ROLE_CREATABLE_BY`, `ROLE_RANK`.
`Nomina` è la fonte di verità multi-ruolo (`attiva + scadenza`).
- Admin solo da Admin; Segreteria da Admin; IABR da Admin/Segreteria.
- Segreteria/IABR devono essere capi; CSQ solo ragazzi; PGV/CRP solo capi.
- `nomina()`: check esclusività CSQ prima del check categoria.

## Convenzioni di codice
- **ruff** + **mypy** configurati in `pyproject.toml`. `pre-commit` disponibile.
- Type hints dove sensato; docstring brevi in italiano per le parti di dominio.
- Una migrazione per ogni cambio di modello; non editare migrazioni già applicate.
- Test con **pytest + pytest-django**; copri FSM, permessi e regole di visibilità.
- Niente segreti nel repo: tutto via `.env*`.

## Deploy e backup

### Deploy in produzione
**Accesso SSH**: `ssh admin.agescicampania.org` — cartella di lavoro `/srv/plancia`.
Claude Code ha accesso diretto via SSH e può eseguire il deploy autonomamente.

`sudo systemctl reload plancia` non è utilizzabile da SSH non interattivo (richiede password
interattiva). Usare sempre **docker compose** direttamente:

```bash
# 1. Aggiorna il codice
git pull

# 2. Ricostruisce le immagini (--no-cache garantisce che il nuovo codice sia incluso)
docker compose --env-file .env.prod build --no-cache web worker beat

# 3. Aggiorna i file statici sull'host (PRIMA di avviare i container — il bind mount
#    ./staticfiles sovrascrive il collectstatic baked nell'immagine)
docker compose --env-file .env.prod run --rm web uv run python manage.py collectstatic --noinput

# 4. Ricrea i container con le nuove immagini (l'entrypoint applica le migrate automaticamente)
docker compose --env-file .env.prod up -d web worker beat
```

**Importante:**
- Usare sempre `up -d` (non `restart`): `restart` riavvia i container con la vecchia immagine senza ricrearli.
- `build` senza `--no-cache` può usare layer in cache e non includere nuovi file (es. migrazioni).
- Le migrate vengono applicate automaticamente dall'entrypoint al primo avvio del container.
- **`collectstatic` va eseguito al passo 3**, prima di `up -d`: `./staticfiles` è un bind mount
  sull'host che persiste tra i deploy. Se eseguito dopo `up -d`, il container web carica il
  vecchio manifest e serve i vecchi hash degli asset anche se i file sono stati aggiornati.

### Deploy in staging
**Cartella**: `/srv/staging.plancia`. Branch `v2-offline`.

Apache su staging serve `/static/` da `staticfiles-staging/` (non `staticfiles/`). Il bind mount
del compose scrive sempre in `staticfiles/`, quindi il collectstatic va eseguito due volte:
1. con volume override → aggiorna `staticfiles-staging/` (file che Apache serve)
2. senza override → aggiorna `staticfiles/staticfiles.json` (manifest che Django legge in memory)

Se manca il secondo step, Django emette URL con hash vecchi e il browser carica CSS sbagliati
(es. versione del tema priva delle classi sidebar) pur avendo i file corretti su disco.

```bash
git pull
docker compose --env-file .env.staging build --no-cache web worker beat
# 1. Aggiorna staticfiles-staging/ (Apache)
docker compose --env-file .env.staging run --rm \
  -v /srv/staging.plancia/staticfiles-staging:/app/staticfiles \
  web uv run python manage.py collectstatic --noinput
# 2. Aggiorna staticfiles/ (manifest Django — OBBLIGATORIO dopo ogni cambio tema)
docker compose --env-file .env.staging run --rm \
  web uv run python manage.py collectstatic --noinput
docker compose --env-file .env.staging up -d web worker beat
```

Il symlink `.env.prod → .env.staging` è necessario perché `docker-compose.yml` referenzia
`env_file: [.env.prod]` nei servizi — è già presente su staging.

**Volume DB staging**: il `docker-compose.yml` definisce il volume `plancia_db`, che Docker Compose
prefissa col nome progetto → `stagingplancia_plancia_db`. Esiste anche `stagingplancia_plancia_staging_db`
(vecchio nome, da una versione precedente del compose) che contiene il dump anonimizzato della
produzione. Se staging appare vuoto dopo un `up -d`, il container DB sta usando `plancia_db` (vuoto)
invece di `plancia_staging_db` (con i dati). Recovery:
```bash
# Verifica quale volume è montato
docker inspect stagingplancia-db-1 --format '{{range .Mounts}}{{.Name}}{{end}}'

# Se è plancia_db (vuoto): ferma lo stack, avvia pg_old sull'altro volume, dump e restore
docker compose --env-file .env.staging stop web worker beat
docker run -d --name pg_old -v stagingplancia_plancia_staging_db:/var/lib/postgresql/data -p 127.0.0.1:5434:5432 postgres:17
sleep 4
docker exec stagingplancia-db-1 psql -U plancia_staging -d postgres -c 'DROP DATABASE plancia_staging;' -c 'CREATE DATABASE plancia_staging OWNER plancia_staging;'
docker exec pg_old pg_dump -U plancia_staging plancia_staging | docker exec -i stagingplancia-db-1 psql -U plancia_staging plancia_staging
docker rm -f pg_old
docker compose --env-file .env.staging up -d web worker beat
```

### Verifica post-deploy
```bash
docker compose --env-file .env.prod logs web --tail=30
```

Backup: `deploy/backup.sh` via cron (`deploy/crontab.example`).

## PDF diari

PDF = moduli 1–5 (CSQ) + Relazione finale CRP (modulo 6). Mai l'esito della valutazione.
Accessibile solo a CRP, Incaricati EG e Admin — non al Capo Squadriglia.

- **`genera_pdf_diario(diario, include_relazione=True)`** in `apps/exports/service.py`
- **Lock anti-duplicati**: chiave Redis `pdf_task_lock:{diario_pk}` (TTL 30 min); impostata
  in `DiarioPdfView.get()`, rilasciata in `finally` nel task.
- **Log**: `LogTaskExport` (model `apps/exports/models.py`); visibile in `/impostazioni/log-export/`.
- **Compressione immagini**: `_compress_image_for_pdf()` riduce a 480px prima dell'embedding.
- **Errori**: notifica email al richiedente e agli Admin con traceback.
- **Generazione massiva**: `task_genera_pdf_massivo` in `apps/exports/tasks.py`; lock Redis
  `pdf_task_lock_massivo:{edizione_pk}` (TTL 2h). Blocca i PDF singoli durante la generazione.
  UI in `/impostazioni/cache-pdf/`.
- **Progress bar**: il task chiama `self.update_state(state="PROGRESS", meta={progresso, completati, totale})`
  ad ogni diario; il task_id è salvato in Redis `pdf_massivo_task_id:{edizione_pk}`. Endpoint polling:
  `GET /impostazioni/task-progresso/<task_id>/` → JSON. JS nella pagina cache-pdf fa polling ogni 2s.
- **Link al PDF**: usare sempre `target="_blank" rel="noopener"`, **mai** l'attributo `download`.
  Il backend imposta già `Content-Disposition: attachment` (basta per far scaricare il file su
  desktop/Android). Su iOS, in modalità standalone (PWA installata), la WebView non ha la toolbar
  di Safari: l'attributo `download` forza la navigazione dentro la WebView e apre un'anteprima a
  schermo intero senza alcun modo per tornare indietro o condividere il file. `target="_blank"`
  delega l'apertura al browser di sistema (Safari), che fornisce la sua toolbar completa.

## Allegati

- Resize automatico al caricamento: `_resize_immagine()` in `apps/diaries/views.py`
- Dimensione configurabile: `Impostazioni.allegati_max_px` (default 1024px)

## Gestione errori HTTP

- **404**: `config.error_views.page_not_found` → `templates/404.html` + email agli ADMINS via `mail_admins()`.
- **500**: `config.error_views.server_error` → `templates/500.html` (standalone, non estende base.html).
  Email agli ADMINS gestita da `AdminEmailHandler` in `LOGGING["loggers"]["django.request"]`.
- **CSRF**: `config.error_views.csrf_failure` (impostato via `CSRF_FAILURE_VIEW`) → `templates/403_csrf.html`.
- **403 generico**: `templates/403.html` (permessi negati, non CSRF).
- **Configurazione admin**: variabile d'ambiente `ADMIN_EMAILS` (lista separata da virgola).
  `SERVER_EMAIL` per il mittente delle notifiche. Se `ADMIN_EMAILS` è vuota, le notifiche sono disabilitate.

## Cosa NON fare
- Non cambiare `AUTH_USER_MODEL` né l'app label dopo le prime migrazioni.
- Non rendere visibili valutazioni/relazioni oltre i ruoli previsti.
- Non implementare WhatsApp (resta un adapter stub dietro `Notifier`).
- Non versionare CSV reali (dati minori): usare solo `fixtures/`.
- Non rendere il codice socio editabile a mano; validarlo come numerico 4–8 cifre.
- Non aggiungere `{% if messages %}` nei template (il tema li gestisce globalmente).
- Non usare i vecchi blocchi v1 `navbar`, `nav_items`, `breadcrumb`, `subnav` (rimossi nel tema v2).
- Non usare `class="footer-agesci mt-auto"` (il footer v2 è gestito interamente dal tema).
- Non usare `<i class="bi bi-*">`: usare `{% bs_icon %}`.
- Non usare `mt-5` sul footer: usare `mt-auto`.
