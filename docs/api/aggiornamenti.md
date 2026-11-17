# API Fase 2 — Aggiornamenti del server dal web

Router `apps/api/routers/aggiornamenti.py`, logica in `apps/aggiornamenti/services.py`
(app `apps.aggiornamenti`: modelli `ReleaseGitHub` e `RichiestaAggiornamento`). Tutti gli
endpoint sono **solo Admin** (`richiedi_admin`) e restano raggiungibili anche con la
manutenzione attiva (bypass in `MaintenanceModeMiddleware`: i permessi li controlla il router).

Perché un'app nuova e non campi in `Impostazioni`: lo storico delle richieste è un audit trail
con più righe (non entra in un singleton), la release ha un suo ciclo (task beat, errori) e
`Impostazioni` è già molto ampio; tenerli separati evita di toccare le sue sezioni esistenti.

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/api/v1/aggiornamenti` | Admin | Versione installata, ultima release (note markdown), `aggiornamento_disponibile`, `richiesta_in_corso` |
| POST | `/api/v1/aggiornamenti/controlla` | Admin | Controlla subito GitHub (sincrono, timeout 10 s); risponde come il GET; un errore di GitHub va in `ultima.errore` |
| POST | `/api/v1/aggiornamenti/richiesta` | Admin + riautenticazione | `{versione: "vX.Y.Z"}` → 201 richiesta; 401 `riautenticazione_richiesta`; 409 richiesta già aperta; 422 versione non valida/non ultima/non successiva; 503 cartella non scrivibile |
| POST | `/api/v1/aggiornamenti/richiesta/annulla` | Admin | Annulla la richiesta aperta se il runner non l'ha presa (`in-corso.json` assente); 409 altrimenti, 422 se non c'è nulla |
| GET | `/api/v1/aggiornamenti/stato` | Admin | Legge `stato.json`, aggiorna lo storico, restituisce `{installata, richiesta, stato, in_corso}` |
| GET | `/api/v1/aggiornamenti/storico` | Admin | Storico delle richieste (paginato `limit`/`offset`) |

Task Celery beat `aggiornamenti.controlla_ultima_release` (ogni giorno alle 04:17, in
`CELERY_BEAT_SCHEDULE`): `GET https://api.github.com/repos/AGESCI-Campania/plancia/releases/latest`,
token facoltativo `GITHUB_TOKEN_RELEASES` (.env), timeout 10 s; gli errori sono loggati e salvati
in `ReleaseGitHub.errore`, mai rilanciati.

## Condizioni per richiedere l'aggiornamento

1. ruolo attivo Admin (o superuser);
2. **autenticazione recente**: nella sessione c'è un login o una riautenticazione allauth più
   recente di `ACCOUNT_REAUTHENTICATION_TIMEOUT` (default 300 s);
3. `versione` nel formato `^v\d+\.\d+\.\d+$`, **uguale** all'ultima release nota
   (`ReleaseGitHub.versione`) e **maggiore** della versione installata (`pyproject.toml`);
4. nessuna richiesta `in_attesa`/`in_corso` e nessun `richiesta.json`/`in-corso.json` nella cartella.

### Riautenticazione dalla SPA (allauth 65.22 headless, client `browser`)

Se `POST /richiesta` risponde `401 {"detail": ..., "riautenticazione_richiesta": true, "flussi": [...]}`:

1. `flussi` elenca i flussi allauth disponibili per l'utente (gli stessi che allauth headless
   mette nelle sue risposte 401): `{"id": "reauthenticate"}` (password),
   `{"id": "mfa_reauthenticate", "types": ["totp", "recovery_codes", "webauthn"]}`,
   `{"id": "reauthenticate_by_code", "recipients": [...]}`.
2. Preferire la MFA (gli Admin la hanno obbligatoria):
   - TOTP / codice di recupero: `POST /_allauth/browser/v1/auth/2fa/reauthenticate` `{"code": "123456"}`;
   - passkey: `GET` poi `POST /_allauth/browser/v1/auth/webauthn/reauthenticate`;
   - altrimenti password: `POST /_allauth/browser/v1/auth/reauthenticate` `{"password": "..."}`.
   Tutte con header `X-CSRFToken` (cookie `csrftoken`). Risposta 200 = riautenticato.
3. Ripetere `POST /api/v1/aggiornamenti/richiesta` entro 5 minuti.

Un Admin entrato con SSO Sestante senza password locale né MFA non ha flussi di
riautenticazione: deve rifare il login SSO (anche un login recente vale come riautenticazione).
L'app mobile (`X-Session-Token`) usa gli stessi endpoint sotto `/_allauth/app/v1/`.

## Contratto dei file (cartella `AGGIORNAMENTI_DIR`)

`settings.AGGIORNAMENTI_DIR` (env `AGGIORNAMENTI_DIR`, default `BASE_DIR/aggiornamenti`, cioè
`/app/aggiornamenti` nel container = bind mount di `/opt/plancia/aggiornamenti`, in `.gitignore`).
Tutti i file sono JSON UTF-8 e vanno scritti **in modo atomico** (file temporaneo nella stessa
cartella + `rename`/`mv`), così chi legge non vede mai un file a metà.

| File | Chi lo scrive | Chi lo legge | Significato |
|---|---|---|---|
| `richiesta.json` | Django | runner (unit `.path`) | richiesta nuova, non ancora presa |
| `in-corso.json` | runner (`mv richiesta.json in-corso.json`) | Django (solo esistenza) | aggiornamento preso in carico / in corso |
| `stato.json` | `aggiorna.sh --stato-file` | Django (`GET /stato`) | avanzamento ed esito |
| `log/` | runner | amministratore | log completi delle esecuzioni |

### `richiesta.json` (Django → host)

```json
{
  "id": 12,
  "versione": "v2.5.0",
  "richiesta_da": "admin@example.org",
  "richiesta_at": "2026-11-16T20:15:03.123456+00:00"
}
```

Il runner deve validare `versione` (regex `^v[0-9]+\.[0-9]+\.[0-9]+$`, tag esistente dopo
`git fetch --tags`) e rifiutare tutto il resto; se la rifiuta scrive `stato.json` con
`esito: "fallito"` (o `"annullato"`) e lo stesso `id`, poi rimuove `in-corso.json`.

### `stato.json` (host → Django)

```json
{
  "id": 12,
  "versione": "v2.5.0",
  "fase": "build",
  "messaggio": "Costruzione delle immagini",
  "percentuale": 40,
  "esito": null,
  "aggiornato_at": "2026-11-16T21:20:00+01:00",
  "log": ["…", "ultime righe, al massimo 200"]
}
```

| Campo | Tipo | Note |
|---|---|---|
| `id` | intero | **obbligatorio**: l'`id` di `richiesta.json`; senza, lo stato non viene associato allo storico |
| `versione` | stringa | tag in aggiornamento |
| `fase` | stringa (≤ 40) | suggerite: `presa_in_carico`, `download`, `novita`, `manutenzione`, `backup`, `build`, `avvio`, `verifica`, `rollback`, `fine` |
| `messaggio` | stringa (≤ 500) | testo per l'utente, in italiano |
| `percentuale` | intero 0–100, facoltativo | |
| `esito` | `null` \| `"completato"` \| `"fallito"` \| `"annullato"` | `null` finché è in corso; valorizzato **solo alla fine** |
| `aggiornato_at` | ISO 8601 con fuso | ora dell'ultima scrittura; con l'esito diventa `completato_at` nello storico |
| `log` | lista di stringhe | ultime righe significative (Django ne conserva al massimo 200) |

Regole di sincronizzazione (`services.sincronizza_storico`, a ogni `GET /stato` e `GET /aggiornamenti`):

- `stato.json` di una richiesta aperta: copia `fase`, `messaggio`, `percentuale`, `log`; con
  `esito` finale chiude la richiesta (`completato|fallito|annullato`, `completato_at`), altrimenti
  la porta `in_corso`;
- `stato.json` assente, illeggibile o di una richiesta già chiusa: la richiesta aperta passa
  `in_attesa → in_corso` se esiste `in-corso.json`; lo storico chiuso non si riscrive mai;
- al termine il runner rimuove `in-corso.json` e **lascia** `stato.json` (la pagina mostra l'esito).

Durante l'aggiornamento `aggiorna.sh` attiva la manutenzione (`manage.py manutenzione attiva
--messaggio "…"`): la pagina continua a interrogare `GET /api/v1/aggiornamenti/stato`
(raggiungibile in manutenzione); quando i container ripartono `installata` diventa la nuova
versione e la SPA ricarica. Se l'API non risponde per qualche secondo (riavvio) la SPA riprova.

## Manutenzione

`uv run python manage.py manutenzione attiva [--messaggio "..."] | disattiva | stato`
(`stato` stampa `attiva` o `disattiva`). Usa lo stesso flag `Impostazioni.manutenzione` del
middleware (nuovo campo `Impostazioni.manutenzione_messaggio`, migrazione `siteconfig/0016`).
In produzione la cache è Redis condivisa, quindi il cambio vale subito per tutti i worker;
in sviluppo (cache locale per processo) il server di sviluppo può vederlo fino a 5 minuti dopo.
Con la manutenzione attiva le API rispondono `503 {"detail": "<messaggio>", "maintenance": true}`
ai non superuser, tranne `/api/v1/sito` e `/api/v1/aggiornamenti/…`.
