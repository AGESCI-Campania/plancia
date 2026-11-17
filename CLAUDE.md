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
- Python **≥ 3.14**, Django **≥ 6.1**. PostgreSQL **≥ 18**. Redis + **Celery** per job asincroni.
- **uv** per dipendenze/venv. **WeasyPrint** (PDF), **openpyxl** (Excel), **odfpy** (export ODS).
- **Interfaccia**: solo la **SPA Vue** in `frontend/` (servita da nginx). Django è solo backend:
  API, allauth headless, admin, email, PDF, callback OAuth (vedi "URL serviti da Django").
- **REST API**: **django-ninja** (OpenAPI automatico, type-driven), **django-cors-headers**
  (CORS solo per l'app mobile), **allauth headless** (`HEADLESS_ONLY`: client *browser* per la
  SPA, *app* con `X-Session-Token` per l'app mobile).
- Auth: **django-allauth** (email + social Google/Microsoft/Apple + **SSO Sestante**, **MFA**), **django-guardian**
  (object-level), **django-axes** (brute-force), **django-hijack** (solo helper/segnali per
  l'impersonazione via API, nessun URL).
- Social login (guida: `docs/guide/social_auth.md`). SSO OIDC con Sestante (guida: `docs/guide/sso_sestante.md`,
  contratto: `docs/INTEGRAZIONE-SSO.md` del repo `sestante`). Drive OAuth (guida: `docs/guide/google_drive_oauth.md`).
  Un provider social senza client id non viene configurato (non compare nella SPA, app avviabile).
  **Apple Sign In**: `key`=TEAM_ID, `secret`=KEY_ID — la versione precedente aveva i campi scambiati
  causando 401 al callback; non invertire.

## Layout
```
config/         # settings/base|dev|prod, urls, celery
apps/           # accounts org editions diaries evaluations notifications
                # storage_drive exports helpdesk stats siteconfig imports
                # api (REST: auth, permissions, schemas/, routers/)
frontend/       # SPA Vue (vedi "Frontend")
templates/      # solo email (mail/, account/email/), PDF (exports/), pagine predefinite
                # (siteconfig/default_pages/), pagine d'errore e manutenzione statiche
scripts/        # installa.sh, aggiorna.sh, backup.sh, _comune.sh (copia dal frontend), _plancia.sh
deploy/         # entrypoint.sh, nginx/default.conf.template (nginx interno, solo HTTP)
fixtures/       # CSV sintetici (NIENTE dati reali)
docs/           # specifica di progetto; docs/api/ (REST API)
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
uv run python manage.py popola_demo --password '<pwd>' [--ricrea] [--disattiva-rate-limit]
# dati demo sintetici e idempotenti (utenti <ruolo>@example.org, Capo Squadriglia con codice
# 990101, staff con TOTP e bypass 000000); solo con DEBUG
cd frontend && npm install && npm run dev   # SPA su :5173 (vedi "Frontend")
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
| `exports` | PDF WeasyPrint + Excel openpyxl + ODS/CSV riassuntivo diari, tasks Celery |
| `storage_drive` | `DriveCredenziali`, `DriveFile`, service `carica_file/crea_cartella` |
| `siteconfig` | `Impostazioni` (singleton), `FooterLink`, `GmailSMTPCredenziali`, `PaginaStatica` |
| `imports` | `LogImportazione`, `RigaImportazione`, commands `import_coca/ragazzi/squadriglie/risposte_eg` |
| `helpdesk` | `Ticket`, `RispostaTicket` |
| `stats` | dashboard per zona |

### URL serviti da Django (`config/urls.py`)
Tutto il resto è la SPA (nginx, fallback `index.html`). Restano: `/api/v1/` (ninja),
`/_allauth/` (headless), `/accounts/<provider>/login/callback/` (con `HEADLESS_ONLY` allauth
monta solo le callback dei provider; Sestante: `/accounts/oidc/sestante/login/callback/`, c'è un
test), `/admin/`, `/healthz/`, `/drive/oauth/callback/` e `/impostazioni/gmail-smtp/oauth/callback/`
(tornano alla SPA con `?esito=…`; l'avvio è via API), `/anymail/webhook/`, i proxy
`/mailadmin/` e `/celery/` (solo Admin, CSP larga `CSP_STRUMENTI`). Gli endpoint della PWA 2.x
(`/api/diari/…`, `/api/soci/`) non esistono più: l'app mobile e la SPA usano solo `/api/v1`.
Nessun context processor di Plancia: i template rimasti (email, PDF) ricevono il contesto
esplicitamente.

**REST API** (`apps/api/`, Plancia 3: l'API copre TUTTE le funzioni, la SPA usa solo `/api/v1`):
- `api.py` — istanza `NinjaAPI`, montaggi router, `registra_gestori(api)`
- `errors.py` — `ErroreSchema`/`ErroreValidazioneSchema` e gestori globali: nei router basta
  **sollevare** `PermessoNegato`/`PermissionDenied` (403), `StatoNonValido`/`AzioneNonConsentita`
  (422), `ObjectDoesNotExist` (404), `ValidationError` (422 con `errori` per campo)
- `auth.py` — `PlanciaAuth`: legge `X-Session-Token` (allauth headless app-mode) o cookie sessione
- `permissions.py` — `is_staff_plancia`, `richiedi_ruolo/staff/admin`, `puo_vedere_diario`
  (delega a `diari_visibili`), `puo_vedere_valutazione`. Le regole sui diari stanno in
  `apps/diaries/permessi.py` (`puo_modificare_moduli`, `puo_scaricare_pdf`, …)
- `schemas/`, `routers/` — un modulo per dominio: `system`, `me`, `utenti`, `org`, `edizioni`,
  `diari`, `valutazioni` (su `/diari`), `drive`, `notifiche`, `impostazioni`, `importazioni`,
  `helpdesk`, `statistiche`, `sito` (pubblico), `aggiornamenti` (solo Admin)
- La logica è nei **servizi** di dominio, usati dai router (e da comandi/task):
  `apps/<app>/services.py` (accounts, org, editions, imports, helpdesk, stats, siteconfig),
  `apps/diaries/service.py`, `apps/notifications/service.py`, `apps/storage_drive/{oauth,service}.py`.
  Nuove funzioni: nel servizio, non nel router. I form rimasti (`apps/editions/forms.py`,
  `apps/siteconfig/forms.py`) servono solo alla validazione nei servizi (nessuna resa HTML).
- Test API: `apps/api/tests/conftest.py` (`utenti` per ruolo, `client_di(ruolo)`, `edizione`,
  `diario`, `json_body`); il rate limit API è disattivato in tutti i test da `conftest.py`
  (marker `rate_limit` per riattivarlo).
- `apps/aggiornamenti` — ultima release GitHub (task beat `controlla_ultima_release`) e storico
  delle richieste di aggiornamento dal web; contratto dei file con lo script host in
  `docs/api/aggiornamenti.md` (`AGGIORNAMENTI_DIR`). `manage.py manutenzione attiva|disattiva|stato`.

Documentazione API: `docs/api/overview.md` (auth, ruoli, rate limiting, errori) · `docs/api/endpoints.md` (indice per dominio: `utenti.md`, `diari.md`, `edizioni.md`, …) · OpenAPI su `/api/v1/docs`.

## Frontend (SPA, Plancia 3 — `frontend/`)
Vue 3.5 + TypeScript 6 + Vite 8 + vue-router 5 + Pinia 4 + Dexie 4 + vite-plugin-pwa 2,
**Bootstrap 6 alpha** (pin esatto) con i partial SCSS del tema AGESCI 3.0.0a3 copiati in
`frontend/src/theme/` (non modificarli: ricopiarli; stili propri in `plancia.scss`).
```bash
cd frontend && npm install
npm run dev            # :5173, proxy verso Django :8000 (vite.config.ts → PERCORSI_BACKEND)
npm run typecheck && npm run lint && npm test
npm run api:tipi       # rigenera src/api/schema.d.ts dallo schema OpenAPI (manage.py esporta_openapi)
npm run e2e            # Playwright (desktop + iPhone); PLANCIA_E2E_EMAIL/PASSWORD per il login
npm run icone          # icone PWA da docs/icona-pwa/ (non ridisegnarle)
PLANCIA_DEMO_PASSWORD=… npm run manuale:schermate [-- gruppo…]   # screenshot del manuale
```
- **Manuale** (`docs/manuale/*.md`) descrive la SPA; screenshot in `docs/manuale/screenshots/`
  con nomi stabili, rigenerati da `scripts/schermate-manuale.ts` (passi in `admin.md` §
  sviluppatori). Il PDF non si versiona (`make manual` in locale, `release-manual.yml` alla release).
- **Auth**: allauth headless *browser* (`src/api/allauth.ts`), cookie di sessione + `X-CSRFToken`.
  Pagine in `src/views/auth/`; `HEADLESS_FRONTEND_URLS` in settings punta a quelle rotte.
  Operazioni sensibili: `conRiautenticazione*` (`src/composables/riautenticazione.ts`).
- **MFA obbligatoria anche sull'API**: `apps/api/auth.py` risponde 403 `mfa_da_configurare`
  a chi deve configurarla (tranne `/api/v1/me…`); regola unica `adapters.mfa_da_configurare`.
- **Tipi**: `src/api/tipi.ts` dagli schemi generati; nomi delle classi `Schema` dell'API
  **unici** (ninja nomina gli schemi OpenAPI con il nome della classe; c'è un test).
- **Permessi in UI**: solo i flag di `me.menu` e i `puo_*` calcolati dal backend.
- **Versioni**: `__VERSIONE_APP__` da `pyproject.toml`; footer con App/Server
  (`/api/v1/sito.versione`); modale `AggiornamentoApp.vue` se diverse (SW in modalità prompt).
- **Dialog/drawer** Bootstrap 6 sul `<dialog>` nativo (`FinestraDialogo.vue`, sidebar);
  i menu usano la data API di Bootstrap (`import 'bootstrap'` in `main.ts`).
- Componenti: icone `IconaBs` (sprite di bootstrap-icons), mai `<i class="bi">`.
- Campi password: `CampoForm` con `tipo="password"` ha già il pulsante mostra/nascondi (come
  il toggle del tema AGESCI); non rifarlo nelle viste.
- **Abbreviazioni nell'UI**: CSQ/CRP/PGV non devono apparire nell'interfaccia. Usare "Capo
  Squadriglia", "Capo Reparto", "Pattuglia GV". Le abbreviazioni restano solo nel codice.
- **Percorsi del backend** (`/admin/`, `/mailadmin/`, `/celery/`): link con caricamento completo
  della pagina, non rotte del router (l'admin Django manda a `/accesso?next=/admin/…`).
- **Offline (Fase 5, `src/offline/`)**: Dexie (`db.ts`: `letture`, `coda`, `meta`). Moduli e foto
  passano da `trasportoOffline`/`inviaFotoOffline` (`coda.ts`): offline o server giù → coda con la
  stessa `Idempotency-Key`, invio alla riconnessione/primo piano/ogni minuto; conflitti (409) e
  dati rifiutati restano in coda e si risolvono in pagina (`ModificheOffline.vue`). Letture per
  compilare offline con `leggiConCopia` (`letture.ts`). Mai risposte API nel service worker.
  Dati legati all'utente: cancellati al logout (con conferma se c'è coda) e se entra un altro
  utente; a sessione scaduta si cancellano le letture e resta solo la coda.

## Gotchas e trappole

### Modelli e ORM
- **`Diario.pubblicato`** è una property (`pubblicato_at is not None`). Nelle query:
  `pubblicato_at__isnull=False`; per pubblicare: `pubblicato_at = timezone.now()`.
- **`AssegnazionePGV`** ha FK verso `Valutazione` (non `Diario`); `related_name="assegnazioni_pgv"`
  è su `Valutazione` — usare `valutazione.assegnazioni_pgv`.
- **`select_related("utente")`** (non `"user"`) nel queryset Socio: il reverse accessor è `utente`.
- **`Anagrafica`**: ha `crp_*` e `csq_*` (nome, cognome, email, cell). Non ha `email_contatto` né
  `cell_contatto`. `tipo_diario` non è un campo di Anagrafica: sta su `Diario.tipo` (l'API lo
  accetta nel modulo anagrafica e lo salva sul diario).
- **`PostoAzione`** (imprese): campi `chi` (max 200) e `cosa` (max 300); il vecchio `descrizione` è stato
  rimosso in 3.0. La **missione** non ha posti d'azione (non è un'impresa): `PostoAzioneMissione`
  è stato eliminato in 3.0, non reintrodurlo.
- **`EsitoSpecialita`**: ha il campo `chi` (max 120, blank=True) per indicare il membro della
  squadriglia a cui è associata la specialità o il brevetto.
- **`MembroSq`**: `cognome` è blank=True/default="" — l'UI usa solo `nome` (campo unico "Nome e
  cognome"). L'ordinamento è su `["nome"]`. Non usare `cognome` in nuove funzionalità.
- **`Diario.moduli_csq_completi`**: per NUOVO richiede impresa1 + impresa2 + missione; per
  RINNOVO richiede solo impresa1 (impresa2 e missione sono facoltative).
- **`Socio.provvisorio`**: CRP creati automaticamente da `import_squadriglie` quando l'email non
  corrisponde; codice socio `tmpNNNNN`. Vengono sostituiti dalla riconciliazione import.

### Auth e ruoli
- **Impersonazione**: solo via API (`services.avvia_impersonazione`/`termina_impersonazione`,
  che riusano helper e segnali di django-hijack; gli URL di hijack non sono montati). Usa il
  *rango massimo* tra tutti i ruoli attivi del target. La Segreteria non può impersonare chi ha
  nomina Admin.
- **`create_superuser`** crea con `ruolo=csq`; il signal `ensure_superuser_ruolo` corregge a DB
  ma l'oggetto in memoria resta vecchio — fare sempre `admin.refresh_from_db()` nei test.
- **Attivazione CSQ** (`TipoInvito.CODICE_SOCIO`): richiede conferma codice socio AGESCI + email.
  `_attiva_e_login` crea automaticamente `Nomina` se mancante (es. utenti con ruolo diverso preesistente).
- **`crea_o_ottieni_utente_per_socio`**: per CSQ senza email usa placeholder
  `noemail.{codice_socio}@noemail.internal`.
- **Utenti staff senza Socio** (`services.crea_utente_staff`): password inutilizzabile, email
  registrata come verificata, link per impostarla con il reset di allauth
  (`invia_link_password` → `/password/reset/{key}` della SPA). Un invio fallito non blocca la
  creazione: finisce nel log e nel `detail` della risposta.
- **Primo amministratore** (`installa.sh`): `createsuperuser` + `EmailAddress` verificata; con
  `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` un'email non verificata blocca il login (flusso
  `verify_email`, messaggio in `AccessoView.vue`).
- **Login con email o codice socio**: `ACCOUNT_LOGIN_METHODS = {"email", "username"}`; gli utenti
  nati da un Socio hanno `username` = codice socio (i Capi Squadriglia spesso non hanno un'email
  vera); la SPA invia `username` se l'identificativo non contiene "@" (`src/api/allauth.ts`).

### FSM Diario (9 stati)
`non_iniziato` → `in_compilazione` → `relazione_finale` → `inviato` → `in_valutazione` →
`in_revisione`/`approvato`/`non_approvato`/`maggiori_info` → `in_compilazione`.
- Default creazione: `NON_INIZIATO`. Auto-transita a `IN_COMPILAZIONE` al primo salvataggio
  di un modulo CSQ (`service.inizia_se_necessario`, chiamato da moduli e upload allegati).
- Moduli 1–5: editabili in `NON_INIZIATO` e `IN_COMPILAZIONE` (Capo Squadriglia).
- Modulo 6: solo in `RELAZIONE_FINALE` (Capo Reparto).
- **Non** usare `moduli_csq_completi` come guardia — usare `stato == RELAZIONE_FINALE`.
- Cambio referenti: `permessi.STATI_PRIMA_INVIO = (NON_INIZIATO, IN_COMPILAZIONE, RELAZIONE_FINALE)`.
- **Flusso valutazione**: `actions.valuta_direttamente` accetta anche `INVIATO` e chiama
  `diario.avvia_valutazione()` automaticamente — non serve più che l'edizione transiti prima.
  Se c'è una proposta PGV `IN_REVISIONE`, l'Incaricato può comunque sovrascriverla con
  `valuta_direttamente()`. Test in `apps/evaluations/tests/test_flussi.py`.

### Azioni FSM e valutazione — `apps/evaluations/actions.py`

**Unica fonte di verità** per logica di dominio e permessi su transizioni FSM e valutazione.
Usata dai router API. Tre eccezioni (tradotte dai gestori globali di `apps/api/errors.py`):

- `AzioneNonConsentita(ValueError)` — base → 422
- `PermessoNegato(AzioneNonConsentita)` → 403
- `StatoNonValido(AzioneNonConsentita)` → 422

Funzioni esposte: `csq_invia`, `invia`, `riapri`, `assegna_pgv`, `valuta_direttamente`,
`proponi_pgv`, `conferma_proposta`, `rigetta_proposta`, `modifica_valutazione`, `pubblica_esito`,
`pubblica_tutti`.

**Non** replicare controlli di permesso nei router per queste azioni — `richiedi_ruolo`
(`apps/api/permissions.py`) fa il check grossolano (ruolo ammesso?), `actions.py` il check
fine-grained (es. "è il CSQ *di questo* diario?").

### Visibilità diari — `apps/diaries/visibility.py`

`diari_visibili(user) -> QuerySet[Diario]` — unica fonte di verità per filtrare i diari
accessibili per ruolo. Usata dal router API `/diari` e da `puo_vedere_diario`.
Non duplicare questa logica altrove.

### Middleware — MFA e manutenzione

- `MFAEnforcementMiddleware` (`apps/accounts/middleware.py`): sui percorsi Django rimasti
  (`/admin/`, `/mailadmin/`, `/celery/`, callback) risponde **403** con la pagina statica
  `templates/403_mfa.html` a chi ha `mfa_da_configurare` (la MFA si configura dalla SPA, Profilo
  → Sicurezza). Esclusi `/_allauth/`, `/api/v1/` (lì vale la regola di `apps/api/auth.py`: 403
  `mfa_da_configurare` tranne `/api/v1/me…`), `/accounts/`, statici, `/healthz/`, `/anymail/`.
  Regola unica: `adapters.mfa_da_configurare` (esenzioni: DEBUG/`SKIP_MFA_ENFORCEMENT`,
  impersonazione, sessione Sestante).
- **Admin Django**: `admin.site.login` reindirizza a `/accesso?next=/admin/…` della SPA
  (password + MFA via allauth); il form password dell'admin non si usa.
- `MaintenanceModeMiddleware` (`apps/siteconfig/middleware.py`): JSON
  `{"detail": "...", "maintenance": true}` (503) su `/api/v1/` e `/_allauth/`, pagina statica
  `templates/siteconfig/manutenzione.html` sugli altri percorsi Django. Restano raggiungibili
  admin (e i superuser), `/accounts/`, `/healthz/`, `/api/v1/sito`, `/api/v1/aggiornamenti`.
  La SPA legge la manutenzione da `/api/v1/sito`. Non aggiungere redirect HTML su `/api/v1/`.

**Middleware API** (in `apps/siteconfig/middleware.py`, attivi solo su `/api/v1/`):
- `ApiRateLimitMiddleware` — fixed-window Redis; conta per sessione esistente (token o cookie), altrimenti per IP reale (`_chiave_client`);
  limiti (per minuto e per ora) configurabili in `Impostazioni`; risponde `429` con `Retry-After`.
- `AppVersionMiddleware` — legge `X-App-Version`; blocca con `426` se < `app_versione_minima`;
  aggiunge `X-App-Upgrade-Warning: true` se < `app_versione_deprecata`; inietta
  `request.app_version` e `request.app_update_available` per uso nei router.

Ordine in `MIDDLEWARE`: entrambi **dopo** `CorsMiddleware` e **prima** di `SessionMiddleware`.

### Drive e OAuth
- **PKCE obbligatorio** (da ottobre 2024): `storage_drive.oauth.avvia_oauth_drive` (da
  `POST /api/v1/drive/oauth`) genera `code_verifier/challenge` e li salva in sessione;
  `DriveOAuthCallbackView` li passa a `fetch_token(code_verifier=...)` e torna alla SPA.
  Stesso schema per Gmail SMTP (`siteconfig.services.url_autorizzazione_gmail` /
  `GmailSMTPOAuthCallbackView`).
- **`Edizione.cartelle_configurate`** blocca **irreversibilmente** `drive_folder_allegati_id`,
  `drive_folder_output_id` e `cartella_diario_format` una volta valorizzati tutti e tre.
- **`carica_pdf_diario`** (in `storage_drive/service.py`): chiama sempre
  `genera_pdf_diario(diario, include_relazione=True)` e, prima di caricare il nuovo file,
  elimina il `DriveFile` precedente da Drive (un solo PDF per diario nella cartella di output).
- **Rinomina cartelle**: `diaries.service.rinomina_squadriglia` usa
  `service.files().update(fileId=folder_id, body={"name": nuovo_nome})` per rinominare le
  cartelle Drive quando si cambia il nome della squadriglia dall'anagrafica.

### Compatibilità Python 3.14 / Django 6
- **`timezone.utc`** non esiste più: usare `datetime.timezone.utc` oppure `timezone.UTC` (il modulo
  `django.utils.timezone` espone `UTC` come alias). Dove serve un epoch sentinel usare
  `timezone.datetime.min.replace(tzinfo=timezone.UTC)`.

### SSO Sestante
- Provider `openid_connect` con id `sestante`, callback `/accounts/oidc/sestante/login/callback/`
  (registrata nel blueprint `provider-plancia.yaml` del repo `sestante`: non cambiarla da sola).
- Ruoli globali (`admin-multipiattaforma` → Admin, `segreteria` → Segreteria) = `Nomina` con
  `da_sso=True`, create/revocate a ogni login SSO da `_sync_ruoli_globali`. Le Nomine locali non si toccano.
- MFA: si salta solo se `sessione_da_sestante(request)` (metodo di login della sessione), **mai**
  in base all'esistenza di un `SocialAccount` collegato.
- Il login locale resta attivo: non disattivarlo senza conferma esplicita dell'utente.
- `SOCIAL_SESTANTE_SERVER_URL` senza `/` finale (in `base.py` c'è `.rstrip("/")`): allauth aggiunge
  `/.well-known/openid-configuration` e con la doppia barra authentik dà 404 (500 al login SSO).
- Login rifiutato (senza email, email duplicata): `_rifiuta_login` torna a
  `/accesso?errore=<messaggio>` della SPA.

### allauth headless
- `HEADLESS_ONLY = True`: nessuna pagina allauth di Django. I link delle email e i redirect
  dei provider vanno alle pagine della SPA in `HEADLESS_FRONTEND_URLS` (obbligatori).
  `LOGIN_URL = "/accesso"` (SPA) per admin e proxy.
- Niente `ACCOUNT_FORMS`: il login headless non li usa. Le email di allauth passano da
  `PlanciaAccountAdapter.send_mail` (template da DB se presenti, altrimenti
  `templates/account/email/`).

### Email
- **Dual backend**: `email_backend_standard` (sistema/inviti singoli) vs `email_backend_massivo`
  (inviti bulk). `email_mode` sovrascrive tutto. Django 6.1 **`MAILERS`**: alias `default`,
  `standard`, `massivo` (tutti `PlanciaEmailBackend`, che chiama `get_connection_per_tipo`).
  Inviare con `msg.send(using="standard")` o `mailers["massivo"]`; **mai** `connection=`,
  `fail_silently=` né impostazioni `EMAIL_*` (deprecate; con `MAILERS` definito sono errori).
  SMTP di riserva in `settings.SMTP_RISERVA`, modalità simulata in `EMAIL_SIMULATO_DIR`.
  I backend costruiti in `email_backends.py` ricevono sempre `alias=`.
- **Container non root**: utente `plancia` con uid/gid di `agesci` (`APP_UID`/`APP_GID`,
  esportati da `scripts/_plancia.sh`, build args nel compose).
- **Anymail signals** in `notifications/webhooks.py`, registrati in `NotificationsConfig.ready()`.
  Webhook: `/anymail/webhook/`.
- **Dev**: Mailpit su `localhost:8025`. `ACCOUNT_EMAIL_VERIFICATION = "none"` in `dev.py`.
- **Dev MFA**: obbligo disattivato quando `DEBUG=True` (`mfa_da_configurare`). Bypass TOTP: `000000`.
- **Passkey (WebAuthn)**: `allauth.mfa.webauthn` in `INSTALLED_APPS`, `MFA_SUPPORTED_TYPES=["totp","recovery_codes","webauthn"]` (obbligatorio — senza questa impostazione `webauthn` non compare in `SUPPORTED_TYPES`), `MFA_PASSKEY_LOGIN_ENABLED=True`, `MFA_PASSKEY_SIGNUP_ENABLED=False`. Usa `fido2` già incluso nell'extra `mfa` di allauth — nessuna dipendenza aggiuntiva. Nessuna migrazione necessaria (stessa tabella `allauth_mfa_authenticator`).
- **MFA selettiva**: `Impostazioni.mfa_obbligatoria_ruoli_estesi` (default True). Se False, MFA obbligatoria solo per Admin; Segreteria e Incaricati EG possono accedere senza. `ruolo_richiede_mfa()` in `adapters.py` legge questa impostazione.

## Regole di dominio
- **Visibilità**: Relazione finale e Valutazione mai visibili al Capo Squadriglia; Valutazione non
  visibile finché non pubblicata. Protezione a tre livelli: UI (SPA), API (router/permessi),
  queryset.
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
- **ruff** + **mypy** configurati in `pyproject.toml` (puliti su tutto il repo: tenerli così;
  le librerie senza tipi sono in `[[tool.mypy.overrides]]`). `pre-commit` disponibile.
- Type hints dove sensato; docstring brevi in italiano per le parti di dominio.
- Migrazioni: Plancia 3.0 si installa con DB vuoto e parte da migrazioni rigenerate
  (`0001_initial` per app, più `0002_initial` per accounts e diaries per le FK incrociate).
  Nessuna data migration: Impostazioni si crea al primo `Impostazioni.get()`, template email e
  pagine predefinite si leggono da file finché non sono salvati in DB. Da qui in poi: una
  migrazione per ogni cambio di modello; non editare migrazioni già applicate.
- Test con **pytest + pytest-django**; copri FSM, permessi e regole di visibilità.
- Niente segreti nel repo: tutto via `.env*`.

## Deploy e backup

### Server
Server dedicato alle piattaforme `*.agescicampania.net` (Ubuntu 26.04, niente Virtualmin/Apache).
Repo clonato in **`/opt/plancia`**, proprietario l'utente **`agesci`** (gruppo `docker`, senza sudo
né SSH: ci si entra con `sudo -iu agesci` da un utente amministratore). URL
`https://plancia.agescicampania.net`. Il vecchio server `admin.agescicampania.org` (`/srv/plancia`)
non è più la produzione.

Regole vincolanti (leggerle prima di toccare compose, nginx, impostazioni HTTP o script):
- frontend/reverse proxy: <https://raw.githubusercontent.com/AGESCI-Campania/agesci-campania-web-frontend/main/docs/INTEGRAZIONE.md>
- SSO: <https://raw.githubusercontent.com/AGESCI-Campania/sestante/main/docs/INTEGRAZIONE-SSO.md>

In sintesi:
- **Caddy** (repo `agesci-campania-web-frontend`) termina TLS e inoltra a `plancia-nginx:80`
  sulla rete esterna `agesci-proxy`. Il blocco `caddy/sites/plancia.caddy` sta in **quel** repo:
  non modificarlo da qui, proporlo all'utente.
- Solo il servizio `nginx` è su `agesci-proxy`; **nessuna porta pubblicata**; niente TLS/certbot
  nel progetto; l'nginx interno inoltra `X-Forwarded-Proto $http_x_forwarded_proto` (non `$scheme`).
- Ogni servizio ha `restart: unless-stopped`; tutti tranne `beat` hanno un `healthcheck`
  (il web su `/healthz/`, con `Host` di `ALLOWED_HOSTS` e `X-Forwarded-Proto: https`).
- Variabili in **`.env`** (creato da `.env.template`; letto da compose per interpolazione ed
  `env_file`). Nuova variabile → aggiungerla a `.env.template` (vuota + commento): `aggiorna.sh`
  la segnala e si ferma finché non è in `.env`. `DATABASE_URL` è composta nel compose.
- Statici: WhiteNoise + `collectstatic` nel `Dockerfile` (manifest nell'immagine). Niente bind
  mount `staticfiles/`, niente `collectstatic` nei comandi di deploy.
- Migrazioni: solo il container `web` le applica all'avvio (`ESEGUI_MIGRAZIONI=1`, `deploy/entrypoint.sh`).
- IP del client: in produzione `AXES_CLIENT_IP_CALLABLE` legge il penultimo `X-Forwarded-For`
  (Caddy → nginx); non tornare a `REMOTE_ADDR`, sarebbe l'nginx interno per tutti.

### Script (`scripts/`, eseguiti da `/opt/plancia` come `agesci`)
- `installa.sh` — prima installazione: `.env` con segreti (`openssl rand`, mai sovrascritto),
  build, `up -d`, attesa `healthy`, primo superutente (`PLANCIA_ADMIN_EMAIL=… scripts/installa.sh`
  per non rispondere alla domanda; password mostrata una volta), unit systemd, passi manuali.
- `aggiorna.sh [vX.Y.Z]` — passa a una release (tag; repo in detached HEAD): albero pulito,
  novità dal `CHANGELOG.md`, controllo variabili nuove, manutenzione, **backup DB** in
  `backups/`, checkout del tag, build, `up -d`, attesa `healthy`, ritorno automatico alla
  versione precedente se la nuova non risponde, unit systemd aggiornate.
- `backup.sh` — DB + `.env` + media in un archivio; timer `plancia-backup.timer` alle 02:30.
- `_comune.sh` è una **copia identica** di quello di `agesci-campania-web-frontend` (e di
  Sestante): non modificarlo qui, riallinearlo copiandolo. Funzioni Plancia in `_plancia.sh`.
- Bash `set -euo pipefail`, `shellcheck -x scripts/*.sh` senza errori, bit eseguibile committato.

### Avvio al boot
Unit `plancia.service` generata da `installa_servizio_systemd plancia "$UNIT_PROXY"` (oneshot,
`docker compose up -d --wait`, dopo `agesci-campania-web-frontend.service`; niente `ExecStop`,
niente dipendenza da Sestante). Senza sudo gli script stampano il comando che un
amministratore deve eseguire. Per fermare in manutenzione: `docker compose stop`.

### Deploy di una nuova versione
Dal Mac: versione in `pyproject.toml`, sezione `## X.Y.Z — AAAA-MM-GG` in `CHANGELOG.md`
(manuale e screenshot aggiornati), commit su `main`, poi tag e GitHub Release **insieme**:
```bash
git tag vX.Y.Z && git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes "<sezione del CHANGELOG.md>"
```
La release va pubblicata **prima** di aggiornare il server: `aggiorna.sh` installa i tag
(il più alto, o quello indicato) e la pagina Impostazioni → Aggiornamenti legge l'ultima
release GitHub. Le release 1.x/2.x (sperimentazione, senza dati reali) sono *pre-release*.
Poi sul server (o da Impostazioni → Aggiornamenti):
```bash
ssh <admin>@<server>
sudo -iu agesci
cd /opt/plancia && scripts/aggiorna.sh
```
Mai `sudo`/root dentro `/opt/plancia` (git: "dubious ownership"). Verifica:
`docker compose ps`, `docker compose logs --tail 50 web`, `curl -I https://plancia.agescicampania.net`.

## PDF diari

PDF = moduli 1–5 (CSQ) + Relazione finale CRP (modulo 6). Mai l'esito della valutazione.
Accessibile solo a CRP, Incaricati EG e Admin — non al Capo Squadriglia.

- **`genera_pdf_diario(diario, include_relazione=True)`** in `apps/exports/service.py`
- **Lock anti-duplicati**: chiave Redis `pdf_task_lock:{diario_pk}` (TTL 30 min); impostata
  da `diaries.service.avvia_generazione_pdf` (`POST /api/v1/diari/{id}/pdf`), rilasciata in
  `finally` nel task.
- **Log**: `LogTaskExport` (model `apps/exports/models.py`); `GET /api/v1/impostazioni/log-export`,
  pagina SPA `/impostazioni/log-export`.
- **Compressione immagini**: `_compress_image_for_pdf()` riduce a 480px prima dell'embedding.
- **Errori**: notifica email al richiedente e agli Admin con traceback.
- **Generazione massiva**: `task_genera_pdf_massivo` in `apps/exports/tasks.py`; lock Redis
  `pdf_massivo_lock:{edizione_pk}` (TTL 2h, preso con `cache.add`). Blocca i PDF singoli durante la generazione.
  API `/api/v1/impostazioni/cache-pdf…`, pagina SPA `/impostazioni/cache-pdf`.
- **Progress bar**: il task chiama `self.update_state(state="PROGRESS", meta={progresso, completati, totale})`
  ad ogni diario; il task_id è salvato in Redis `pdf_massivo_task_id:{edizione_pk}`. Polling:
  `GET /api/v1/impostazioni/task/{task_id}`.
- **PDF nella SPA**: pagina `/diari/<pk>/pdf` (stato con `GET /api/v1/diari/{id}/pdf/stato`,
  file con `GET /api/v1/diari/{id}/pdf`); i link nelle email puntano lì.
- **Excel esiti**: `GET /api/v1/edizioni/{id}/esiti-excel`, generato al volo da
  `genera_excel_edizione()`. Sempre sincrono.
- **Export riassuntivo diari**: `GET /api/v1/edizioni/{id}/export-diari?formato=xlsx|ods|csv`.
  Foglio unico con tutti i moduli (visibilità filtrata per ruolo), `genera_export_diari()` in
  `apps/exports/service.py`. Async ibrido: CSV sempre sync; xlsx/ods → sync se diari ≤
  `EXPORT_DIARI_SOGLIA_ASYNC` (default 50), altrimenti task Celery + email. **Non confondere**
  con l'export Esiti: quello è solo voti/esiti; questo contiene tutto il contenuto dei moduli.

## Allegati

- Resize automatico al caricamento: `ridimensiona_immagine()` in `apps/diaries/service.py`
  (usato anche da `import_risposte_eg`)
- Dimensione configurabile: `Impostazioni.allegati_max_px` (default 1024px)

## Gestione errori HTTP

`config/error_views.py`: sui percorsi Django pagine **HTML statiche autonome** (CSS inline,
niente `{% extends %}`, niente DB: `templates/403.html`, `404.html`, `500.html`,
`403_csrf.html`, `403_mfa.html`, `siteconfig/manutenzione.html`, stile di
`frontend/public/errore-servizio.html`); su `/api/` e `/_allauth/` JSON `{"detail": …}`.
- **404**: notifica agli ADMINS via `mail_admins()`. **500**: email da `AdminEmailHandler`
  (`LOGGING["loggers"]["django.request"]`). **CSRF**: `CSRF_FAILURE_VIEW`.
- **CSP** (`config/settings/prod.py`, `SECURE_CSP` + `ContentSecurityPolicyMiddleware`): vale per
  le risposte di Django (admin, errori, callback, API); la CSP della SPA la imposta nginx.
- **Configurazione admin**: variabile d'ambiente `ADMIN_EMAILS` (lista separata da virgola).
  `SERVER_EMAIL` per il mittente delle notifiche. Se `ADMIN_EMAILS` è vuota, le notifiche sono disabilitate.

## Cosa NON fare
- Non cambiare `AUTH_USER_MODEL` né l'app label dopo le prime migrazioni.
- Non rendere visibili valutazioni/relazioni oltre i ruoli previsti.
- Non implementare WhatsApp (resta un adapter stub dietro `Notifier`).
- Non versionare CSV reali (dati minori): usare solo `fixtures/`.
- Non rendere il codice socio editabile a mano; validarlo come numerico 4–8 cifre.
- Non reintrodurre viste/template Django per l'interfaccia: tutto passa da SPA + `/api/v1`.
- Non cambiare la callback di Sestante `/accounts/oidc/sestante/login/callback/`.
- Non far dipendere le pagine d'errore/manutenzione da tema, `{% extends %}` o DB.
- Non duplicare logica di visibilità diari fuori da `diari_visibili()` (`apps/diaries/visibility.py`).
- Non duplicare logica di permessi/stato per FSM e valutazione fuori da `apps/evaluations/actions.py`.
- Non aggiungere redirect HTML su path `/api/v1/` nei middleware — rispondere con JSON o bypass.
- Non confondere export Esiti (`genera_excel_edizione`) con export Diari (`genera_export_diari`): sono due cose distinte.
