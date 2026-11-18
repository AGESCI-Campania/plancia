# API Fase 2 — Importazioni

Router `apps/api/routers/importazioni.py`, logica in `apps/imports/services.py` (usata anche
dai comandi `import_*`). Ruoli: **Admin, Segreteria, Incaricati EG**; gli altri 403, anonimo 401.

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/api/v1/importazioni/tracciati` | staff | Tracciati: `coca`, `ragazzi`, `squadriglie` (edizione obbligatoria), `risposte_eg` (.xlsx, edizione facoltativa) |
| POST | `/api/v1/importazioni/lancia/{tracciato}` | staff | `multipart/form-data`: `file`, `edizione_pk`. 202 `{tracciato, task_id, messaggio}`; 422 per tracciato/file/estensione/edizione non validi |
| GET | `/api/v1/importazioni/log` | staff | Storico paginato (`limit`, `offset`, filtro `tipo`) |
| GET | `/api/v1/importazioni/log/{id}` | staff | Dettaglio con `righe_da_riconciliare` e `righe_scartate` (dati grezzi, socio abbinato, note) |
| GET | `/api/v1/importazioni/log/{id}/scarti.csv` | staff | CSV delle righe scartate (UTF-8 con BOM, `Content-Disposition: attachment`) |
| POST | `/api/v1/importazioni/righe/{id}/riconcilia` | staff | `{socio_pk}` (Socio capo) → riga `ok`, Capo Reparto sostituito sul diario; 422 se la riga non è da riconciliare o il socio non è un capo |
| POST | `/api/v1/importazioni/log/{id}/riprova` | staff | Riprova l'abbinamento dei Capi Reparto (solo log `squadriglie`, altrimenti 422) → `{messaggio, risolte, ancora_aperte, log}` |

Note: `coca`/`ragazzi`/`squadriglie` girano in Celery e scrivono un `LogImportazione`;
`risposte_eg` invia l'esito per email agli Admin (nessun log). Il `task_id` è l'id Celery.
La SPA mostra gli scarti nella pagina `/import/{id}` e scarica il CSV da `scarti.csv`.
