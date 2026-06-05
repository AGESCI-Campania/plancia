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
- **uv** per dipendenze/venv. **Bootstrap 5** lato frontend via **`django-agesci-campania-theme` 1.1.0**.
  Icone SVG inline con **`django-bootstrap-icons`**. **WeasyPrint** (PDF), **openpyxl** (Excel).
- Auth: **django-allauth** (email + social Google/Microsoft/Apple, **MFA**, log sessioni).
  Permessi object-level con **django-guardian**, brute-force con **django-axes**.
- PWA con **django-pwa** + service worker/IndexedDB costruiti sopra.
- File su **Google Drive** via OAuth (guida: `docs/guide/google_drive_oauth.md`).
- Social login Google/Microsoft/Apple (guida: `docs/guide/social_auth.md`).

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

**UI**: usa `django-agesci-campania-theme` **1.1.0** (installato). Template estendono `base.html` → `agesci_theme/base.html`. Setting: `AGESCI_THEME_BRANCA = "eg"`.

**CRITICO — navbar e blocchi del tema**: `{% block %}` nei template `{% include %}` **non** partecipano
all'ereditarietà Django. Il tema usa `{% include "agesci_theme/partials/navbar.html" %}`, quindi
`{% block brand_text %}` e `{% block nav_items %}` al suo interno sono opachi. Per personalizzare la
navbar, sovrascrivere **completamente** `{% block navbar %}` in `base.html` senza usare `{{ block.super }}`
per la parte delle voci. Vedi `templates/base.html` come riferimento.

**`{% block messages %}` globale (tema 1.1.0)**: il tema gestisce automaticamente i messaggi Django
nel blocco `{% block messages %}` di `agesci_theme/base.html`. **Non aggiungere `{% if messages %}`
nei singoli template** — causerebbe messaggi duplicati. Il blocco può essere sovrascritto se serve
posizionarlo diversamente in un template specifico.

**Icone — `django-bootstrap-icons`**: tutti i template usano icone SVG inline via
`{% load bootstrap_icons %}` + `{% bs_icon "nome-icona" size="14" extra_classes="..." %}`.
Le SVG vengono scaricate da CDN al primo uso e cachate in `.icon_cache/` (esclusa da `.gitignore`).
Non usare `<i class="bi bi-*">` né il CDN Bootstrap Icons via `<link>`.

**Footer sticky**: il footer in `{% block footer %}` di `templates/base.html` usa `class="footer-agesci mt-auto"`.
Il `mt-auto` è **obbligatorio** per il corretto funzionamento del layout sticky del tema
(`body { height: 100vh; d-flex flex-column }`). Non sostituire con `mt-5` o margini fissi.

App con modelli e UI completi:
- **`accounts`** — `User` (+ `socio` OneToOneField), `Nomina`, `LoginEvent`; `roles.py` (+ service `nomina()`); `signals.py` (+ `ensure_superuser_ruolo`: imposta automaticamente `ruolo=ADMIN` quando `is_superuser=True` viene salvato — corregge il default CSQ di `createsuperuser`); `mixins.py`; `forms.py` (Bootstrap mixin + form allauth); `views.py` (`ProfiloView`, `UtenteListView`, `UtenteDetailView`, `NominaView`, `CambiaRuoloView`, `CreaUtenteDaSocioView`); `urls.py` (namespace `accounts`, mountato su `utenti/`). Template: `accounts/profilo|utente_list|utente_detail`. Test: `apps/accounts/tests/`.
  **`CreaUtenteDaSocioView`** (POST `/utenti/crea-da-socio/`): Admin/Segreteria/IABR creano un `User` attivo a partire da un `Socio(capo)` già importato e assegnano il ruolo tramite `service_nomina()`. Il form è nella pagina `/utenti/` con autocomplete Tom Select 2 sull'endpoint `/api/soci/?categoria=capo`. I ruoli nominabili sono filtrati in base a `ROLE_CREATABLE_BY` (anche in `UtenteListView.get_context_data` → `ruoli_nominabili`).
  **Multi-ruolo**: un utente può avere più ruoli simultanei (sorgente: `Nomina.attiva + Nomina.scadenza`). `User.ruolo` = ruolo attivo corrente; `User.ruoli_attivi` = lista chiavi; `User.ruoli_attivi_choices` = lista (chiave, etichetta). `CambiaRuoloView` (POST `/utenti/cambia-ruolo/`) cambia il ruolo attivo. La navbar mostra un selettore se l'utente ha >1 ruolo attivo. Eccezione: CSQ e altri ruoli non possono coesistere nella stessa edizione (controllato in `nomina()`). Scadenza opzionale per PGV, IABR, Segreteria: campo `Nomina.scadenza` (DateField). `create_superuser` crea l'utente con `ruolo=csq` di default → il signal `ensure_superuser_ruolo` lo corregge a DB, ma **l'oggetto in memoria resta con il vecchio valore**: fare sempre `admin.refresh_from_db()` dopo `create_superuser` nei test.
- **`org`** — `Zona`, `Gruppo`, `Reparto`, `Squadriglia`, `Socio`; autocomplete `GET /api/soci/?q=&categoria=` (login required).
  `Socio.provvisorio` (BooleanField): `True` per i CRP creati automaticamente da `import_squadriglie` quando l'email non corrisponde a nessun Socio esistente. Il codice socio è `tmpNNNNN` (5 cifre, prefisso `tmp`) — formato distinto dai codici ufficiali (solo numerici 4–8 cifre). `Socio.genera_codice_tmp()` genera il prossimo codice tmp disponibile. I record provvisori vengono sostituiti dalla riconciliazione import; se il CRP provvisorio ha attivato l'account, lo `User` viene trasferito al Socio reale e il provvisorio viene eliminato.
- **`editions`** — `Edizione` (FSM 4 stati), `Dilazione`; CRUD views + template. Namespace `editions`.
  Campi evento: `data_evento_inizio`/`fine`, `evento_comune` (autocomplete comuni-ita), `evento_localita`.
  Drive: `drive_folder_allegati_id` (ex `foto`), `drive_folder_output_id`, `drive_oauth_account`.
  **Cartelle Drive per diario**: `cartella_diario_format` (CharField, default `{id_univoco}_{edizione}_{nome_gruppo}_{nome_reparto}_{nome_squadriglia}_{specialita}`) — formato del nome delle sottocartelle per i diari; variabili disponibili: `{id_univoco}` (obbligatorio, PK diario zero-padded 5 cifre), `{edizione}`, `{nome_gruppo}`, `{nome_zona}`, `{nome_reparto}`, `{nome_squadriglia}`, `{specialita}`.
  `Edizione.cartelle_configurate` (property): `True` quando `drive_folder_allegati_id`, `drive_folder_output_id` e `cartella_diario_format` sono tutti non-vuoti — **blocca irreversibilmente** la modifica di quei tre campi. La UI su `/edizioni/<pk>/modifica/` mostra la sezione Drive in sola lettura quando `cartelle_configurate=True`; `DriveEdizioneFolderUpdateView` rifiuta la POST con errore se il lock è attivo.
  `HomeView` (root `/`): reindirizza all'edizione con stato `APERTA`/`IN_VALUTAZIONE` più recente per anno; se nessuna attiva mostra `templates/home_no_edizione.html`.
- **`diaries`** — `Diario` (FSM **8 stati**), moduli 1–6, `Allegato`; views + template. Namespace `diaries`. Test FSM + visibilità: `apps/diaries/tests/`.
  **FSM stati**: `in_compilazione` → (CSQ: `csq_invia()`) → `relazione_finale` → (CRP: `invia()`) → `inviato` → `in_valutazione` → `in_revisione`/`approvato`/`non_approvato`/`maggiori_info` → `in_compilazione` (riapertura). Il Capo Reparto può compilare il modulo 6 **solo** nello stato `relazione_finale`; i moduli 1–5 del Capo Squadriglia sono editabili **solo** in `in_compilazione`.
  `DiarioInviaView` detecta lo stato corrente: se `IN_COMPILAZIONE` chiama `csq_invia()`, se `RELAZIONE_FINALE` chiama `invia()`.
  `_puo_editare()` controlla `stato == IN_COMPILAZIONE` (solo Capo Squadriglia). `_puo_editare_relazione()` controlla `stato == RELAZIONE_FINALE` (solo Capo Reparto).
  Costanti ufficiali in cima a `models.py`: `SPECIALITA_SQUADRIGLIA` (12, Allegato 3), `SPECIALITA_INDIVIDUALI` (66, Allegato 2), `BREVETTI_COMPETENZA` (15, Allegato 4).
  `Anagrafica.specialita` usa queste choices. `MembroSq.ruolo` ha choices `RuoloSq` (csq/vcsq/squadrigliere/altro). `SentieroCammino` ha valori `scoperta/competenza/responsabilita/non_specificato`.
  `EsitoSpecialita` ha campo `tipo` (`TipoEsito.SPECIALITA` / `TipoEsito.BREVETTO`); i form impresa usano due formset separati (`SpecialitaFormSet` + `BrevettoFormSet`) con prefissi `specialita`/`brevetti`.
  `Anagrafica` **non ha più** `email_contatto` e `cell_contatto` (rimossi — migrazione `0004`).
  **Cambio referenti** (`_STATI_PRIMA_INVIO = (IN_COMPILAZIONE, RELAZIONE_FINALE)`):
  - `CambiaCsqView` (GET/POST `/diari/<pk>/cambia-csq/`): accessibile al CRP referente del diario quando `stato == IN_COMPILAZIONE`; accessibile a Admin/Segreteria/IABR (`is_staff_plancia`) quando `stato in _STATI_PRIMA_INVIO`. Valida `Socio.categoria == "ragazzo"` e `provvisorio == False`. Redirect → `diaries:detail`.
  - `CambiaCrpView` (GET/POST `/diari/<pk>/cambia-crp/`): solo Admin/Segreteria/IABR, quando `stato in _STATI_PRIMA_INVIO`. Valida `Socio.categoria == "capo"` e `provvisorio == False`. Redirect → `diaries:detail`.
  - `CambiaCrpRepartoView` (GET/POST `/diari/reparto/<reparto_pk>/cambia-crp/`): solo Admin/Segreteria/IABR; aggiorna in bulk il CRP di tutti i diari del reparto con `stato in _STATI_PRIMA_INVIO`. Redirect → `diaries:list`.
  - `DiarioDetailView.get_context_data` popola `puo_cambiare_csq` e `puo_cambiare_crp` per mostrare i pulsanti nel template `detail.html`.
  - Template: `diaries/cambia_csq.html`, `diaries/cambia_crp.html`, `diaries/cambia_crp_reparto.html` — usano Tom Select 2 via CDN con AJAX su `/api/soci/?q=&categoria=`.
  - **Bug fix pregresso** in `apps/org/views.py`: `select_related("utente")` (non `"user"` — il reverse accessor da `User.socio` con `related_name="utente"` è `utente` su `Socio`); analogamente `utente__ruolo` e `s.utente.pk`.
  **Sottocartelle Drive per diario**: `Diario.drive_folder_allegati_id` e `Diario.drive_folder_output_id` — ID delle sottocartelle Drive personali, create automaticamente da `assicura_cartelle_diario()`. Allegati: `StatoSync` choices `LOCALE/IN_CODA/CARICATO`; `AllegatoUploadView` imposta `stato_sync=IN_CODA` e dispatcha `task_carica_allegato_drive.delay(pk)` se l'edizione ha Drive configurato.
  **`apps/diaries/service.py`**: `sanitizza_nome_cartella(s)` (rimuove diacritici, spazi→`_`, caratteri vietati, tronca a 100 car.), `calcola_nome_cartella_diario(diario)` (applica il formato dell'edizione con i dati del diario), `valida_formato_cartella(fmt)` (verifica presenza `{id_univoco}` e assenza di variabili sconosciute).
- **`notifications`** — `MailTemplate`, `Invito` (token UUID + `tipo` + delivery tracking), `TipoInvito`, `DeliveryStatus`, `render_mail()`; service + tasks Celery + webhooks anymail. Namespace `notifications`. Template default in `templates/mail/`.
  **`TipoInvito`**: `STANDARD` (link email diretto, per CRP/PGV) | `CODICE_SOCIO` (link consegnato dal CRP al CSQ; l'attivazione richiede conferma codice socio AGESCI + email).
  **Delivery tracking**: campi `provider_message_id`, `delivery_status` (`DeliveryStatus` choices: in_attesa/inviato/consegnato/bounce/spam/fallito), `delivery_error` su `Invito`. Aggiornati da `handle_post_send` (cattura message_id dopo invio) e `handle_tracking` (bounce/delivery via webhook) in `apps/notifications/webhooks.py`. Richiedono un provider anymail configurato. Visualizzati in `gestione_inviti.html` via `_delivery_badge.html`.
  **Flusso inviti per edizione**: `invia_inviti_capi_per_edizione(edizione)` (Admin/Segreteria/IABR) invia i link ai CRP. `invia_inviti_csq_per_edizione(edizione)` crea inviti CSQ di tipo `CODICE_SOCIO`, invia al CRP una email riepilogativa con tabella (template `invito_crp_csq_lista`) e tenta invio diretto al CSQ se ha email valida.
  **`GestioneInvitiView`** (`GET /notifiche/inviti/`): dashboard con contatori (da invitare / inviato / attivato) e tabella per squadriglia con badge delivery. **`InviaInvitiEdizoneView`** (`POST /notifiche/inviti/invia/`): avvia il task bulk (`tipo=capi|csq`). **`InvitiCrpView`** (`GET /notifiche/inviti/miei/`): accessibile al solo Capo Reparto — elenca le proprie squadriglie con stato dell'invito al Capo Squadriglia e pulsante "Reinvia" (chiama `ReinvioInvitoView` che ora ammette anche `Ruolo.CRP` per i propri inviti).
  **Attivazione CSQ**: `AttivazoneInvitoView` — per `TipoInvito.CODICE_SOCIO` mostra il form `notifications/conferma_codice_socio.html` (GET), valida codice socio + email (POST), aggiorna `User.email`/`Socio.email` se placeholder o diversa, poi autentica.
  **`crea_o_ottieni_utente_per_socio(socio, ruolo)`**: crea lo `User` se non esiste; per CSQ senza email usa il placeholder `noemail.{codice_socio}@noemail.internal`.
  **`AnymailMessage`**: `service.py` usa `AnymailMessage` (con fallback a `EmailMessage` se anymail non installato); imposta `msg.metadata = {"invito_pk": str(invito.pk)}` per il tracking. Il metadata è ignorato dai backend SMTP.
- **`evaluations`** — `Valutazione`, `AssegnazionePGV`; views per PGV/Incaricato (assegna, proponi, conferma, rigetta, pubblica). Namespace `evaluations`.
  **Nota modello**: `AssegnazionePGV` ha FK verso `Valutazione` (non verso `Diario`); `related_name="assegnazioni_pgv"` è su `Valutazione`. Usare `valutazione.assegnazioni_pgv` nelle query, non `diario.assegnazioni_pgv`.
- **`exports`** — PDF WeasyPrint (`genera_pdf_diario`), Excel openpyxl (`genera_excel_edizione`), tasks Celery con upload Drive opzionale. Template PDF: `templates/exports/diario.html`.
- **`storage_drive`** — `DriveCredenziali`, `DriveFile`; service `carica_file/pdf/excel`, `crea_cartella`; views OAuth (`DriveOAuthInitView`, `DriveOAuthCallbackView`) + AJAX folder picker (`DriveFolderListView`, `DriveCartellaCreaView`). Namespace `storage_drive`, mountato su `drive/`. Settings: `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI` da env. In dev: `OAUTHLIB_INSECURE_TRANSPORT=1` settato automaticamente nel callback.
  **Funzioni service per sottocartelle diario**:
  - `assicura_cartelle_diario(diario)`: crea su Drive le sottocartelle `drive_folder_allegati_id` e `drive_folder_output_id` del diario (se mancanti) usando il nome calcolato da `calcola_nome_cartella_diario`; salva gli ID sul diario. No-op se l'edizione non ha cartelle principali configurate.
  - `carica_allegato_drive(allegato)`: chiama `assicura_cartelle_diario`, carica il file locale nella sottocartella allegati del diario (fallback: cartella allegati dell'edizione), salva `drive_file_id`, imposta `stato_sync=CARICATO`, elimina il file locale.
  - `carica_pdf_diario(diario)`: chiama `assicura_cartelle_diario`, carica il PDF nella sottocartella output del diario (fallback: cartella output dell'edizione).
  **`storage_drive/tasks.py`**: `task_carica_allegato_drive(allegato_pk)` — task Celery idempotente (skip se già `CARICATO`; in caso di errore reimposta `LOCALE` per permettere retry).
- **`helpdesk`** — `Ticket`, `RispostaTicket`; views CRUD + rispondi/chiudi/prendi. Namespace `helpdesk`.
- **`stats`** — dashboard per zona (esiti, tempi, ticket); visibile a staff. Namespace `stats`.
- **`siteconfig`** — `Impostazioni` singleton, middleware manutenzione, backend email custom; `forms.py` (`ImpostazioniForm` con widget Bootstrap, `MailTemplateForm` con TinyMCE). Namespace `siteconfig`.
  Footer: `footer_testo` (rich text TinyMCE) + modello `FooterLink` (FK → Impostazioni, max 5, campi `tipo` `TipoLink`/`url`/`etichetta`/`ordine`). `TipoLink` choices: `sito_web`, `email`, `facebook`, `instagram`, `tiktok`. I link appaiono nel footer con icona `{% bs_icon %}` corrispondente.
  Context processor `apps.siteconfig.context_processors.impostazioni` inietta `impostazioni` in ogni template: usare `{{ impostazioni.titolo }}` ecc. senza passarlo esplicitamente nelle viste. I link footer si leggono con `{{ impostazioni.footer_links.all }}`.
  **Email provider**: `EmailProvider` choices (smtp / brevo / mailgun / mailersend / postmark / sendgrid / sparkpost / ses). `PlanciaEmailBackend` legge `Impostazioni.email_provider` a runtime: per SMTP usa `SmtpBackend`; per provider transazionali usa `django-anymail` con `override_settings` context manager (thread-safe con Gunicorn sync). `EmailMode.MAILPIT` invia via SMTP a Mailpit interno. Nuovi campi: `email_provider`, `email_provider_api_key`, `email_provider_webhook_secret`.
  **Anymail signals**: `handle_post_send` e `handle_tracking` (in `apps/notifications/webhooks.py`) registrati in `NotificationsConfig.ready()`. Aggiornano `Invito.delivery_status` e `Invito.provider_message_id`. Webhook URL: `/anymail/webhook/` (dispatcher `AnymailWebhookDispatchView` legge il provider da DB con `override_settings`).
  **Mailpit debug**: `EmailMode.MAILPIT` invia via SMTP a Mailpit interno. `MailpitProxyView` (`/mailadmin/`) è un proxy HTTP verso `MAILPIT_INTERNAL_URL`, accessibile solo a `is_staff=True`. Mailpit avviato con `--ui-web-path /mailadmin`. Profilo compose: `mailpit`. Settings: `MAILPIT_INTERNAL_URL`, `MAILPIT_SMTP_HOST`, `MAILPIT_SMTP_PORT`.
  **Invito tracking**: `DeliveryStatus` choices (in_attesa/inviato/consegnato/bounce/spam/fallito); campi `provider_message_id`, `delivery_status`, `delivery_error` su `Invito`. Visualizzati in `notifications/_delivery_badge.html` (incluso in `gestione_inviti.html`).
  Pagina impostazioni suddivisa in sezioni (Identità, Footer, Posta elettronica, Stato, Import, Template email).
  **Gestione MailTemplate da UI**: `MailTemplateEditView` (GET/POST `/impostazioni/mail/<chiave>/`), `MailTemplateImportaView` (POST `/impostazioni/mail/<chiave>/importa/`), `MailTemplateDeleteView` (POST `/impostazioni/mail/<chiave>/elimina/`), `MailTemplateCopiaView` (POST `/impostazioni/mail/<chiave>/copia/` — duplica verso altra chiave). Editor: TinyMCE + sidebar tag copiabili + upload immagini (`MailTemplateImageUploadView` — `@csrf_exempt`, ruolo ≥ Admin/Segreteria/IABR, salva in `media/mail_images/`).
  Partial: `siteconfig/_campo.html`, `siteconfig/_switch.html`.
- **`imports`** — `LogImportazione`, `RigaImportazione`; management commands `import_coca/ragazzi/squadriglie` (upsert idempotente, riconciliazione Capo Reparto); task Celery; view riconciliazione. Namespace `imports`.
  **Gestione errori per record**: ogni command usa `transaction.savepoint()` per isolare i fallimenti per singola riga. Se un record causa un errore DB (valore troppo lungo, violazione unicità, ecc.) il savepoint viene rollbackato, la riga finisce in `SCARTATA` con il messaggio di errore come nota, e l'import prosegue. Il `LogImportazione` viene salvato **prima** di `transaction.atomic()` per sopravvivere a qualsiasi rollback.
  **CRP provvisori**: `import_squadriglie` — se il CRP non viene trovato per email/nome ma i dati del tracciato (nome, cognome, email) sono disponibili, chiama `_crea_crp_provvisorio()` che crea un `Socio(capo, provvisorio=True, codice_socio=tmpNNNNN)`. Il `Diario` riceve comunque un CRP; la riga resta `DA_RICONCILIARE`. **Riconciliazione** (`_aggiorna_diario_crp`): filtra `crp__isnull=True | crp__provvisorio=True`; trasferisce l'eventuale `User` dal provvisorio al Socio reale (`_trasferisci_utente_provvisorio`), poi elimina il provvisorio. `RiprovaAnomalieView` esclude i Socio provvisori dai match automatici (cerca solo tra i non-provvisori).
  **Creazione utenti durante import**: `import_squadriglie` chiama `crea_o_ottieni_utente_per_socio()` dopo ogni riga importata con successo — crea `User` con password inutilizzabile per CSQ e CRP (non provvisori). Gli utenti vengono attivati tramite il normale flusso inviti.
  **Download scarti**: `ScartiCsvView` (`GET /import/<pk>/scarti.csv`) — streaming CSV UTF-8 BOM delle righe `SCARTATA` con colonne `#`, `Errore` + i dati grezzi originali. Accessibile a staff.
  **UI form import**: i box per avviare i tre import (Capi, Ragazzi, Squadriglie) sono nella pagina `/import/` (non più in `/impostazioni/`). `LanciaImportView` resta in `siteconfig` ma redirige a `imports:log_list` dopo l'avvio.
  **Auto-rilevamento delimitatore**: `leggi_csv(path)` (in `import_coca.py`, importata dagli altri command) gestisce automaticamente righe `sep=`, riga `EventoXXXX` in testa e delimitatore via `csv.Sniffer`.
- **`editions`** — management command `archivia_edizione --genera/--purga --conferma`.

**`Diario.pubblicato`** è una property (`pubblicato_at is not None`). Usare `pubblicato_at__isnull=False` nelle query e assegnare `pubblicato_at = timezone.now()` per pubblicare.

Migrazioni create per tutte le app con modelli. Dopo ogni cambio di modello: `uv run python manage.py makemigrations <app>`.

URL montati: `admin/`, `accounts/` (allauth), `utenti/` (accounts app — namespace `accounts`), `hijack/`, PWA, `edizioni/`, `diari/`, `valutazioni/`, `notifiche/`, `helpdesk/`, `impostazioni/`, `import/`, `stats/`, `api/soci/`, `drive/`, `anymail/webhook/` (anymail tracking), `mailadmin/` (Mailpit proxy, solo staff).
`/` → `HomeView` (redirect edizione attiva o pagina "nessuna edizione"); `/__debug__/` (debug toolbar, solo `DEBUG=True`).

Template allauth in `templates/account/` (tutti estendono `base.html`): login, logout, verification_sent, email_confirm, password_reset e varianti, **signup**, **signup_closed**, **password_change**, **password_set**, **email**, **account_inactive**, **reauthenticate**. Form Bootstrap via `ACCOUNT_FORMS` in settings (`apps.accounts.forms`): `PlanciaLoginForm`, `PlanciaSignupForm`, `PlanciaResetPasswordForm`, `PlanciaChangePasswordForm`, `PlanciaSetPasswordForm`, `PlanciaAddEmailForm`.

Template MFA in `templates/mfa/`: `authenticate.html`, `index.html`, `reauthenticate.html`; `totp/activate_form.html`, `totp/deactivate_form.html`; `recovery_codes/index.html`, `recovery_codes/generate.html`.

**Navbar** (`templates/base.html`): role-aware con badge utente (cerchio con iniziale, dropdown Profilo/Email/Password/MFA/Esci). PGV vede "Diari assegnati" (filtrati via `AssegnazionePGV`). Capo Reparto vede voce "Inviti" (`notifications:inviti_crp`) nella barra principale. Banner hijack arancio quando si impersona un utente. Dropdown Gestione (staff): sezione "Persone" include link "Utenti" e "Inviti" (`notifications:gestione_inviti`). Voci Gestione filtrate per ruolo.
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
- **Visibilità**: la Relazione finale del Capo Reparto e la Valutazione non sono **mai** visibili al Capo Squadriglia; la valutazione non è visibile a Capo Squadriglia/Capo Reparto **finché non è pubblicata**. Applica la protezione a tre livelli: UI, view, queryset/serializer.
- **Flusso diario a due fasi**: il Capo Reparto può accedere al modulo 6 **solo** dopo che il Capo Squadriglia ha cliccato "Invia al Capo Reparto" (stato `RELAZIONE_FINALE`). Non usare `moduli_csq_completi` come guardia — usare `stato == RELAZIONE_FINALE`.
- **Rinnovo**: moduli 4 e 5 non obbligatori ma compilabili (decide il Capo Squadriglia). Obbligatori solo se Nuovo.
- **`IN_REVISIONE`** solo per *Approvata*/*Non approvata* proposte da un membro della Pattuglia GV (richiedono conferma Incaricato). *Maggiori informazioni* non passa di lì.
- Gli **Incaricati EG** possono modificare qualunque decisione **fino alla pubblicazione**.
- **Riapertura** per integrazioni solo se valutazione su 1ª scadenza e 2ª non ancora passata.
- **Pattuglia GV** valuta solo i diari assegnati e **non può ri-delegare**.

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
  `categoria_compatibile`) + modello `apps.accounts.models.Nomina` (fonte di verità multi-ruolo).
- Admin creato solo da Admin (+ `createsuperuser`); Segreteria da Admin; IABR da Admin/Segreteria.
- Segreteria e IABR **devono essere capi**; Admin può essere un account senza Socio.
- PGV/CRP solo a *capi*; CSQ solo a *ragazzi* (vincolo validato in fase di nomina).
- `Nomina.attiva` (bool) + `Nomina.scadenza` (DateField opzionale): se `attiva=False` il ruolo è revocato (record mantenuto per audit). Scadenza si usa per PGV, IABR, Segreteria.
- `nomina()` in `roles.py`: check esclusività CSQ **prima** del check categoria; al primo ruolo aggiorna `User.ruolo`, altrimenti non tocca il ruolo attivo.

## Impersonazione (§2)
- Solo **Admin** e **Segreteria** impersonano; il controllo usa il **rango massimo** tra tutti i
  ruoli attivi del target (`_rango_massimo()`), non solo il ruolo corrente.
  (La Segreteria non impersona un utente che ha nomina Admin, anche se opera come CSQ.)
  Ranghi e logica in `apps.accounts.roles` (`ROLE_RANK`, `puo_impersonare`, `can_hijack`).
- Implementata con **django-hijack**: `HIJACK_PERMISSION_CHECK = "apps.accounts.roles.can_hijack"`,
  urls `hijack/`, banner di sessione. Logga ogni impersonazione (audit).
- **Attenzione**: in questa versione di django-hijack il templatetag `{% hijack_button %}` **non esiste**. Il bottone va costruito manualmente con `<form method="post" action="{% url 'hijack:acquire' %}"><input type="hidden" name="user_pk" value="{{ utente.pk }}">`. La libreria `{% load hijack %}` fornisce solo il filtro `|can_hijack`. Il `{% load %}` deve stare in cima al template (fuori da blocchi `{% if %}`).
- **Abbreviazioni nel frontend**: CSQ, CRP e PGV **non devono apparire nell'interfaccia utente**. Usare sempre i nomi completi: "Capo Squadriglia", "Capo Reparto", "Pattuglia GV" / "Pattuglia Guidoncini Verdi". Le abbreviazioni rimangono nei nomi di variabili Python e nei commenti del codice.

## Retention / archiviazione (§7, §12)
- Comando `archivia_edizione` (app `editions`) in due passi su edizioni **chiuse**:
  `--genera` (PDF dei diari + Excel esiti su Drive) e `--purga --conferma` (elimina le **foto** e
  marca l'edizione archiviata; i link esterni restano come testo). Idempotente; la cancellazione è
  loggata. Rifiuta se l'edizione non è chiusa o se gli output non sono su Drive.

## Import: riconciliazione (§14)
- `apps.imports.models.LogImportazione`/`RigaImportazione`: l'import Evento aggancia il CRP per
  **email**; le righe senza match vanno `da_riconciliare` e si correggono dalla **schermata di
  riconciliazione manuale** (accesso Admin/IABR/Segreteria) con autocompletamento Socio(capo).

## Deploy e migrazioni

Il container `web` usa `deploy/entrypoint.sh` come `ENTRYPOINT`: esegue `manage.py migrate --noinput` prima di avviare gunicorn. Le migrazioni vengono quindi applicate automaticamente ad ogni riavvio/rebuild del container.

Flusso deploy standard in produzione (dopo ogni `git pull` con modifiche al codice):
```bash
git pull
sudo systemctl reload plancia    # build nuova immagine + up -d + migrate automatico
```
**Distinzione importante**:
- `systemctl reload` → `docker compose build + up -d` → **ricostruisce l'immagine** con il nuovo codice e ricrea i container; le migrazioni girano nell'entrypoint. Usare per ogni deploy.
- `systemctl restart` → `docker compose down + up -d` senza rebuild → riavvia i container con la **vecchia immagine**; utile solo per riavvii di emergenza senza modifiche al codice.

Se il file `/etc/systemd/system/plancia.service` è ancora quello vecchio (con `restart` in ExecReload), aggiornarlo da `deploy/plancia.service.tpl` con:
```bash
sudo cp deploy/plancia.service /etc/systemd/system/plancia.service
sudo systemctl daemon-reload
```

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
- Non aggiungere `{% if messages %}` nei template: il tema 1.1.0 gestisce i messaggi Django
  globalmente via `{% block messages %}` in `agesci_theme/base.html`.
- Non usare `<i class="bi bi-*">` per le icone: usare `{% bs_icon %}` da `django-bootstrap-icons`.
- Non usare `mt-5` sul footer: usare `mt-auto` per il layout sticky del tema.
