# TODO — Plancia v2.2: REST API + Export riassuntivo diari

## Obiettivo
Esporre una REST API pubblica versionata (`/api/v1/`) per il futuro frontend mobile e
aggiungere un export riassuntivo completo dei diari (xlsx / ods / csv, filtrato per ruolo).

**Piano dettagliato**: `tmp/Plancia_Piano_API_e_Export.md`
**Ricognizione codebase**: eseguita in data 2026-06-28, tutte le assunzioni del piano verificate.

---

## Decisioni (tutte chiuse)

| # | Decisione | Esito |
|---|---|---|
| D1 | Framework API | **django-ninja** (OpenAPI/Swagger automatico, type-driven con mypy) |
| D2 | Auth app native | **allauth headless** (riusa login/MFA/social già configurati, header `X-Session-Token`) |
| D3 | Ampiezza v1 | **Lettura + scrittura completa** (moduli, transizioni FSM, azioni valutazione) |
| D4 | Export | **Foglio unico riassuntivo**, tutti i campi testo, link cartella Drive, formati xlsx/ods/csv |

Allegati binari: in v1 solo metadati + link Drive; upload binario rimandato a v1.1.
Export: solo per-edizione. Async ibrido a soglia (`EXPORT_DIARI_SOGLIA_ASYNC=50`, CSV sempre sync).

---

## Note dalla ricognizione (trovato rispetto al piano)

- `RelazioneFinale` **non ha `version`** → PUT relazione-finale senza optimistic locking
- `PostoAzioneMissione` esiste (campo `descrizione`) → includere nell'export, concatenato
- `_puo_editare()` controlla solo stato + ruolo (non `user.socio`) — da replicare fedelmente
- Middleware MFA e Maintenance **non bypassano** `/api/v1/` né `/_allauth/` → da correggere

---

## Milestone

| # | Milestone | Dipendenze | Stato |
|---|---|---|---|
| M0 | Decisioni chiuse | — | ✅ |
| M1 | Auth headless + bypass middleware | — | ✅ |
| M2 | Scheletro API ninja + `/me` | M1 | ✅ |
| M3 | Read endpoints + `diari_visibili()` | M2 | ✅ |
| M4 | Write moduli diario | M3 | ✅ |
| M5 | Transizioni FSM + azioni valutazione | M3/M4 | ✅ |
| M6 | Export riassuntivo (xlsx/ods/csv) | indipendente | ✅ |
| M7 | Doc, bump versione 2.2.0, tag | M1–M6 | ✅ |

> M6 è indipendente da M1–M5 e può procedere in parallelo.

---

## Piano tecnico per milestone

### M1 — Auth headless + bypass middleware

**Prima di tutto**: verificare `allauth.headless` disponibile:
```bash
uv run python -c "import allauth.headless; print('ok')"
```

- `config/settings/base.py`: aggiungere `"allauth.headless"` a INSTALLED_APPS; settings headless (HEADLESS_ONLY=False, token strategy — verificare nomi esatti dalla doc allauth 65.x)
- `config/urls.py`: `path("_allauth/", include("allauth.headless.urls"))` prima di `accounts/`
- `apps/accounts/middleware.py` — MFAEnforcementMiddleware: bypass su `/api/v1/` e `/_allauth/` (aggiungere ai path esclusi)
- `apps/siteconfig/middleware.py` — MaintenanceModeMiddleware: bypass stesso + restituire 503 JSON (non HTML) su path API

### M2 — Scheletro API ninja + `/me`

Dipendenze: `uv add django-ninja django-cors-headers`

Settings: `"corsheaders"` in INSTALLED_APPS e MIDDLEWARE (prima di CommonMiddleware); `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_CREDENTIALS`.

Struttura nuova app `apps/api/`:
```
apps/api/
  api.py            # NinjaAPI(version="1.0.0", docs_url="/docs")
  auth.py           # SessionTokenAuth: X-Session-Token → user (via allauth headless)
  permissions.py    # is_staff_plancia, puo_vedere_diario, puo_editare_diario, ...
  schemas/          # Pydantic schemas per dominio
  routers/          # me, editions, org, diaries, evaluations
  tests/
```

`config/urls.py`: `path("api/v1/", api.urls)` (separato dai legacy `/api/diari/` e `/api/soci/`)

### M3 — Read endpoints + estrazione logica condivisa

**`apps/diaries/visibility.py`** (nuovo):
```python
def diari_visibili(user) -> QuerySet[Diario]: ...
```
Estrae la logica da `DiarioListView.get_queryset()`. Usata da: list view, API, export.
Estendere `test_visibilita.py` con test diretti sulla funzione.

**`apps/diaries/serialization.py`** (nuovo):
Estrarre da `api_views.py` i helper `_str_field`, `_date_field`, `_validate_nested`, `_sync_nested`, `_anagrafica_data`, `_presentazione_data`, `_impresa_data`, `_missione_data` + aggiungere `_relazione_finale_data`, `_valutazione_data`. `api_views.py` importa da qui — comportamento invariato.

Endpoints read:
- `GET /api/v1/edizioni`, `GET /api/v1/edizioni/{id}`
- `GET /api/v1/org/albero`
- `GET /api/v1/diari` (usa `diari_visibili()`, filtri, paginazione)
- `GET /api/v1/diari/{id}` (contenuto annidato, rispetta visibilità RelazioneFinale e Valutazione)

### M4 — Write moduli diario

Riusa contratto optimistic locking esistente (payload `{version, data}`, 409 su conflitto).
- `PUT /api/v1/diari/{id}/anagrafica`, `.../presentazione`, `.../imprese/{numero}`, `.../missione`
- `PUT /api/v1/diari/{id}/relazione-finale` — no optimistic locking (RelazioneFinale non ha `version`); solo stato==RELAZIONE_FINALE e ruolo==CRP

Permessi (da `permissions.py`, replica `DiarioApiMixin._puo_editare`):
- Moduli CSQ: stato ∈ {NON_INIZIATO, IN_COMPILAZIONE} AND ruolo==CSQ
- Relazione finale: stato==RELAZIONE_FINALE AND ruolo==CRP

### M5 — Transizioni FSM + azioni valutazione

**`apps/evaluations/actions.py`** (nuovo — service condiviso usato da web + API):
```python
def csq_invia(diario, user): ...      # diario.csq_invia()
def invia(diario, user): ...           # diario.invia()
def riapri(diario, user): ...          # diario.riapri() con guard
def assegna_pgv(...): ...
def valuta_direttamente(...): ...
def proponi_pgv(...): ...
def conferma_proposta(...): ...
def rigetta_proposta(...): ...
def modifica_valutazione(...): ...
def pubblica_esito(...): ...
def pubblica_tutti(...): ...
```

View web esistenti refactorate per usare `actions.py`.

Endpoints transizioni: `POST /api/v1/diari/{id}/azioni/{csq-invia|invia|riapri}`
Endpoints valutazione: sotto `/api/v1/diari/{id}/valutazione/` (GET, assegna-pgv, valuta, proposta, conferma, rigetta, modifica, pubblica)

Test: per ogni azione → ruolo ammesso/negato + stato sorgente corretto/errato + effetto diario.

### M6 — Export riassuntivo diari

Dipendenza: `uv add odfpy`

Settings (`config/settings/base.py`):
```python
EXPORT_DIARI_SOGLIA_ASYNC: int = 50
EXPORT_DIARI_CSV_SEMPRE_SYNC: bool = True
```

**`apps/exports/service.py`** (aggiungere, senza toccare `genera_excel_edizione`):
```python
def costruisci_tabella_diari(qs, user) -> tuple[list[str], list[list]]: ...
def genera_export_diari(qs, user, formato) -> tuple[bytes, str, str]: ...  # content, content-type, filename
```

Colonne (foglio unico): Identificazione → Anagrafica CRP/CSQ → Presentazione + Membri (concat) → Impresa 1 (titolo/date/perché/come/cosa/link + posti d'azione concat + esiti concat) → Impresa 2 (stesse) → Missione (titolo/data/desc + posti d'azione missione concat) → Relazione finale (CRP: sintesi 1/2/missione/considerazioni/specialità conquistata) → Valutazione (solo se autorizzato) → Link cartella Drive

Writer: `_write_xlsx` (openpyxl, stile verde 5AA02C), `_write_csv` (stdlib, utf-8-sig), `_write_ods` (odfpy)

View `ExportDiariView` in `apps/editions/views.py`:
`GET /edizioni/<pk>/export-diari/?formato=xlsx|ods|csv`
Con logica ibrida sync/async basata su `EXPORT_DIARI_SOGLIA_ASYNC`.

UI: bottone "Esporta diari" in `editions/detail.html` (accanto a "Esiti Excel"), dropdown formato.

### M7 — Doc & rilascio

- README: badge + sezione API
- CLAUDE.md: stack (ninja, cors, odfpy), `apps/api/`, distinzione export Esiti vs export Diari, bypass middleware, `diari_visibili()`
- `.env.*.example`: nuove variabili
- `mise.toml`: task `openapi-validate`
- **Documentazione API** (`docs/api/`):
  - `overview.md`: autenticazione (sessione web + X-Session-Token), ruoli e visibilità, paginazione, gestione errori, versioning
  - `endpoints.md`: riferimento completo di tutti gli endpoint con esempi di request/response
  - `export.md`: guida all'export riassuntivo diari (formati, soglia async, ruoli)
- Bump versione `2.1.0` → `2.2.0`, tag `v2.2.0`

---

## File da modificare/creare

| File | Operazione |
|---|---|
| `pyproject.toml` | `uv add django-ninja django-cors-headers odfpy` |
| `config/settings/base.py` | INSTALLED_APPS, MIDDLEWARE, nuovi settings |
| `config/urls.py` | `/_allauth/`, `/api/v1/` |
| `apps/accounts/middleware.py` | bypass API |
| `apps/siteconfig/middleware.py` | bypass API, 503 JSON |
| `apps/diaries/api_views.py` | import da `serialization.py` (no logic change) |
| `apps/diaries/serialization.py` | **nuovo** |
| `apps/diaries/visibility.py` | **nuovo** |
| `apps/diaries/views.py` | `get_queryset()` → `diari_visibili()` |
| `apps/diaries/tests/test_visibilita.py` | esteso |
| `apps/evaluations/actions.py` | **nuovo** |
| `apps/evaluations/views.py` | refactor → usa `actions.py` |
| `apps/exports/service.py` | aggiungere costruttore + writer |
| `apps/exports/tasks.py` | aggiungere task export diari |
| `apps/editions/views.py` | aggiungere `ExportDiariView` |
| `apps/editions/urls.py` | URL export |
| `templates/editions/detail.html` | bottone "Esporta diari" |
| `apps/api/` | **nuova app** (api.py, auth.py, permissions.py, schemas/, routers/, tests/) |

---

## Procedura di release (v2.2.0)

1. Lavorare su branch `feat/api-rest-export-completo`
2. `uv run pytest` verde (inclusi nuovi test + non-regressione PWA legacy)
3. `uv run ruff check . && uv run mypy .` puliti
4. PR → `main`, checklist:
   - [ ] `/_allauth/` espone login/MFA/social in app mode
   - [ ] `/api/v1/docs` mostra schema completo
   - [ ] Legacy `/api/diari/` e `/api/soci/` funzionanti
   - [ ] Middleware non fa redirect su path API
   - [ ] Export xlsx/ods/csv corretto per ogni ruolo
   - [ ] Export "Esiti" esistente invariato
   - [ ] Variabili d'ambiente documentate in `.env.*.example`
   - [ ] CLAUDE.md aggiornato
5. Bump `pyproject.toml` → `2.2.0`, tag `v2.2.0`
6. Deploy produzione con procedura standard (CLAUDE.md)
