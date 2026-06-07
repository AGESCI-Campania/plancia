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
- **uv** per dipendenze/venv. **Bootstrap 5** via **`django-agesci-campania-theme` 1.1.0**.
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
| `imports` | `LogImportazione`, `RigaImportazione`, commands `import_coca/ragazzi/squadriglie` |
| `helpdesk` | `Ticket`, `RispostaTicket` |
| `stats` | dashboard per zona |

Autocomplete Socio: `GET /api/soci/?q=&categoria=` (Tom Select 2). URL montati in `config/urls.py`.
Context processor `impostazioni` inietta `Impostazioni` (singleton) in ogni template — usare
`{{ impostazioni.titolo }}` senza passarlo esplicitamente nelle viste.

## Gotchas e trappole

### Template e UI
- **Navbar**: `{% block %}` dentro `{% include %}` non partecipa all'ereditarietà Django. Sovrascrivere
  **completamente** `{% block navbar %}` in `base.html` — no `{{ block.super }}` per le voci.
- **Messages**: tema 1.1.0 gestisce `{% block messages %}` globalmente — **non aggiungere**
  `{% if messages %}` nei template, causerebbe duplicati.
- **Icone**: `{% load bootstrap_icons %}` + `{% bs_icon "nome" %}`. Mai `<i class="bi bi-*">`.
- **Footer**: `class="footer-agesci mt-auto"` — `mt-auto` obbligatorio per il layout sticky.
- **Abbreviazioni nell'UI**: CSQ/CRP/PGV non devono apparire nell'interfaccia. Usare "Capo
  Squadriglia", "Capo Reparto", "Pattuglia GV". Le abbreviazioni restano solo nel codice.

### Modelli e ORM
- **`Diario.pubblicato`** è una property (`pubblicato_at is not None`). Nelle query:
  `pubblicato_at__isnull=False`; per pubblicare: `pubblicato_at = timezone.now()`.
- **`AssegnazionePGV`** ha FK verso `Valutazione` (non `Diario`); `related_name="assegnazioni_pgv"`
  è su `Valutazione` — usare `valutazione.assegnazioni_pgv`.
- **`select_related("utente")`** (non `"user"`) nel queryset Socio: il reverse accessor è `utente`.
- **`Anagrafica`**: non ha `email_contatto` né `cell_contatto` (rimossi — migrazione `0004`).
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

### Drive e OAuth
- **PKCE obbligatorio** (da ottobre 2024): `DriveOAuthInitView` genera `code_verifier/challenge`,
  li salva in sessione; `DriveOAuthCallbackView` li passa a `fetch_token(code_verifier=...)`.
  Stesso pattern per `GmailSMTPOAuth*View`.
- **`Edizione.cartelle_configurate`** blocca **irreversibilmente** `drive_folder_allegati_id`,
  `drive_folder_output_id` e `cartella_diario_format` una volta valorizzati tutti e tre.

### Email
- **Dual backend**: `email_backend_standard` (sistema/inviti singoli) vs `email_backend_massivo`
  (inviti bulk). `get_connection_per_tipo(tipo)` in `email_backends.py`. `email_mode` sovrascrive tutto.
- **Anymail signals** in `notifications/webhooks.py`, registrati in `NotificationsConfig.ready()`.
  Webhook: `/anymail/webhook/`.
- **Dev**: Mailpit su `localhost:8025`. `ACCOUNT_EMAIL_VERIFICATION = "none"` in `dev.py`.
- **Dev MFA**: middleware disabilitato quando `DEBUG=True`. Bypass TOTP: `000000`.
- **MFA selettiva**: `Impostazioni.mfa_obbligatoria_ruoli_estesi` (default True). Se False, MFA obbligatoria solo per Admin; Segreteria e Incaricati EG possono accedere senza. `ruolo_richiede_mfa()` in `adapters.py` legge questa impostazione.

## Regole di dominio
- **Visibilità**: Relazione finale e Valutazione mai visibili al Capo Squadriglia; Valutazione non
  visibile finché non pubblicata. Protezione a tre livelli: UI, view, queryset.
- **Rinnovo**: moduli 4–5 facoltativi (Capo Squadriglia decide); obbligatori solo se Nuovo.
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

# 3. Ricrea i container con le nuove immagini (l'entrypoint applica le migrate automaticamente)
docker compose --env-file .env.prod up -d web worker beat
```

**Importante:**
- Usare sempre `up -d` (non `restart`): `restart` riavvia i container con la vecchia immagine senza ricrearli.
- `build` senza `--no-cache` può usare layer in cache e non includere nuovi file (es. migrazioni).
- Le migrate vengono applicate automaticamente dall'entrypoint al primo avvio del container.

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
- **Log**: `LogTaskExport` (model `apps/exports/models.py`); visibile in Impostazioni.
- **Compressione immagini**: `_compress_image_for_pdf()` riduce a 480px prima dell'embedding.
- **Errori**: notifica email al richiedente e agli Admin con traceback.

## Allegati

- Resize automatico al caricamento: `_resize_immagine()` in `apps/diaries/views.py`
- Dimensione configurabile: `Impostazioni.allegati_max_px` (default 1024px)

## Funzionalità da sviluppare (non ancora implementate)

- **Generazione massiva PDF diari**: task Celery che genera i PDF di tutti i diari
  di un'edizione in batch. Flusso previsto:
  1. Email di avvio al richiedente
  2. Email di progresso ogni 10 diari con i link ai PDF già generati
  3. Email finale con tutti i link
  Vedi `apps/exports/tasks.py` (`task_genera_pdf_diario`) come base.

## Cosa NON fare
- Non cambiare `AUTH_USER_MODEL` né l'app label dopo le prime migrazioni.
- Non rendere visibili valutazioni/relazioni oltre i ruoli previsti.
- Non implementare WhatsApp (resta un adapter stub dietro `Notifier`).
- Non versionare CSV reali (dati minori): usare solo `fixtures/`.
- Non rendere il codice socio editabile a mano; validarlo come numerico 4–8 cifre.
- Non aggiungere `{% if messages %}` nei template (il tema li gestisce globalmente).
- Non usare `<i class="bi bi-*">`: usare `{% bs_icon %}`.
- Non usare `mt-5` sul footer: usare `mt-auto`.
