# API Fase 2 — Diari (`/api/v1/diari`)

Router: `apps/api/routers/diaries.py` · schemi: `apps/api/schemas/diaries.py` ·
regole: `apps/diaries/visibility.py` (chi vede), `apps/diaries/permessi.py` (cosa può fare),
`apps/diaries/service.py` (rinomina, allegati, PDF, referenti), `apps/evaluations/actions.py` (FSM).

Le transizioni (invio Capo Squadriglia, invio Capo Reparto, riapertura) restano
`POST /diari/{id}/azioni/{csq-invia|invia|riapri}` e la valutazione `/diari/{id}/valutazione…`
(router `evaluations.py`): non sono duplicate qui.

Ruoli: **Staff** = Admin, Segreteria, Incaricati EG. **CSQ/CRP del diario** = referente di quel
diario. **PGV** = solo diari assegnati. Ogni endpoint richiede autenticazione (401 altrimenti);
un diario non visibile dà 403, inesistente 404.

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/diari` | tutti (diari visibili) | Lista paginata (`limit`, `offset`). Filtri: `edizione_id`, `zona_id`, `gruppo_id`, `reparto_id`, `stato` (più valori separati da virgola), `tipo`, `specialita`, `q` (nome/cognome di Capo Squadriglia e Capo Reparto, nome squadriglia; ogni parola deve comparire), `ordina` (`squadriglia`, `reparto`, `gruppo`, `zona`, `tipo`, `stato`, `csq`, `crp`, `edizione`, `aggiornato`; `-` = decrescente; più campi separati da virgola; 422 se non valido). Righe con `csq`, `crp`, `specialita`, `puo_pdf` oltre ai campi storici |
| GET | `/diari/moduli/opzioni` | tutti | Scelte per i campi dei moduli: `tipi_diario`, `specialita_squadriglia`, `specialita_individuali`, `brevetti`, `ruoli_squadriglia`, `sentieri`, `stati_specialita`, `moduli_foto` (`{valore, etichetta}` o stringhe) e limiti delle foto `allegati_max_px` (`Impostazioni.allegati_max_px`), `allegati_max_mb`, `allegati_tipi` (MIME ammessi) |
| GET | `/diari/filtri` | tutti | Valori per i filtri (edizioni, zone, gruppi, reparti, specialità presenti tra i diari visibili; stati, tipi, ordinamenti). `edizione_id` facoltativo |
| GET | `/diari/{id}` | visibile | Dettaglio: moduli 1–5, relazione (mai al Capo Squadriglia), valutazione (solo se visibile), `csq`/`crp`, `scadenze`, `stato_moduli` (presenza, obbligatorietà per tipo, `versioni`), `allegati`, `permessi` |
| GET | `/diari/{id}/stato` | visibile | Stato leggero per la compilazione offline (equivale a `GET /api/diari/<pk>/` della PWA) + `versioni` |
| GET | `/diari/{id}/permessi` | visibile | Solo i permessi calcolati (`puo_modificare_moduli`, `puo_vedere_relazione`, `puo_modificare_relazione`, `puo_vedere_valutazione`, `puo_inviare_csq`, `puo_inviare`, `puo_riaprire`, `puo_cambiare_csq`, `puo_cambiare_crp`, `puo_concedere_dilazione`, `puo_caricare_allegati`, `puo_eliminare_allegati`, `puo_pdf`) |
| GET | `/diari/{id}/anagrafica` | visibile | Modulo 1 `{version, data}` (`version: 0` se mai salvato) |
| PUT | `/diari/{id}/anagrafica` | Staff; CSQ del diario in NON_INIZIATO/IN_COMPILAZIONE | `{version, data}`. 409 `{error: "conflict", server_version}`; 400 `{error: "validation", errors}`. Rinomina la squadriglia **e le cartelle Drive**; `tipo_diario` → `Diario.tipo`; email referenti solo da staff |
| GET | `/diari/{id}/presentazione` | visibile | Modulo 2 con membri |
| PUT | `/diari/{id}/presentazione` | come anagrafica | Membri sincronizzati per `id` (senza id = nuovo, assente = eliminato) |
| GET | `/diari/{id}/imprese/{1\|2}` | visibile | Moduli 3–4 con posti d'azione (`chi`/`cosa`), specialità e brevetti (`chi`). 404 se numero ≠ 1, 2 |
| PUT | `/diari/{id}/imprese/{1\|2}` | come anagrafica | Idem, sincronizzazione per `id` |
| GET | `/diari/{id}/missione` | visibile | Modulo 5: titolo, data, descrizione e svolgimento (la missione non ha posti d'azione) |
| PUT | `/diari/{id}/missione` | come anagrafica | Stessi campi |
| GET | `/diari/{id}/relazione-finale` | visibile, non Capo Squadriglia | Modulo 6 `{version, data}` |
| PUT | `/diari/{id}/relazione-finale` | Staff; CRP del diario in RELAZIONE_FINALE (422 negli altri stati) | `{version?, data}`: con `version` 409 sui conflitti, senza (app mobile) nessun controllo. `specialita_conquistata` può essere `null` |
| GET | `/diari/{id}/allegati` | visibile | Elenco foto (`?modulo=impresa_1\|impresa_2\|missione`) con `anteprima_url`, `miniatura_url`, `download_url` |
| POST | `/diari/{id}/allegati` | come i moduli 1–5 | Multipart `modulo`, `file` (jpeg/png/webp/heic, max 20 MB). Ridimensionata a `Impostazioni.allegati_max_px`, in coda per Drive se configurato; primo caricamento → IN_COMPILAZIONE. 201; 422 con `errori` |
| DELETE | `/diari/{id}/allegati/{allegato_id}` | Staff; CSQ del diario fino a RELAZIONE_FINALE; CRP del diario in RELAZIONE_FINALE | 204; 404 se già eliminata |
| GET | `/diari/{id}/allegati/{allegato_id}/anteprima` | visibile | Immagine inline (locale o Drive); `?lato=32..2048` miniatura JPEG |
| GET | `/diari/{id}/allegati/{allegato_id}/file` | visibile | Download (`Content-Disposition: attachment`) |
| GET | `/diari/{id}/pdf/stato` | visibile, non Capo Squadriglia; diario inviato (422 prima) | `{stato, messaggio, sincrono, avviato, download_url}`; `stato` = `pronto` \| `da_generare` \| `in_generazione` (lock `pdf_task_lock:{id}`) \| `bloccato` (generazione massiva) |
| POST | `/diari/{id}/pdf` | come sopra | Avvia il task Celery (202, mail «in generazione») se `da_generare`; altrimenti 200 con lo stato. Lock atomico, rispetta il lock massivo |
| GET | `/diari/{id}/pdf` | come sopra | 200 `application/pdf` se pronto (cache Drive, o generato al volo senza Drive); 202 JSON con lo stato altrimenti (non avvia la generazione) |
| POST | `/diari/{id}/cambia-csq` | Staff prima dell'invio; CRP del diario in NON_INIZIATO/IN_COMPILAZIONE | `{socio_id}` (ragazzo non provvisorio, 422 altrimenti) → `{detail, nuovo, precedente}` |
| POST | `/diari/{id}/cambia-crp` | Staff prima dell'invio | `{socio_id}` (capo non provvisorio) |
| GET | `/diari/reparti/{reparto_id}/cambia-crp` | Staff | Diari non inviati del reparto (quelli che il cambio toccherà) |
| POST | `/diari/reparti/{reparto_id}/cambia-crp` | Staff | `{socio_id}` → `{detail, nuovo, diari_aggiornati}` |

## Idempotenza (coda offline)

I PUT dei moduli e il POST degli allegati accettano l'header `Idempotency-Key`: un secondo invio
con la stessa chiave (stesso utente e percorso, entro 24 ore) restituisce la risposta già data
invece di un 409 o di una foto doppia. Senza header il comportamento è quello di sempre.

## Versioni dei moduli

`version` cresce a ogni salvataggio, dalla SPA come dall'app mobile: due salvataggi concorrenti
dello stesso modulo producono sempre un 409. Anche la relazione finale (modulo 6) ha `version`.

## Mappa PWA 2.x → v1 (gli endpoint `/api/diari/` sono stati rimossi in 3.0)

| Vecchio (PWA) | Nuovo (`/api/v1`) |
|---|---|
| `GET /api/diari/<pk>/` | `GET /diari/{id}/stato` (o `GET /diari/{id}`) |
| `GET /api/diari/<pk>/modulo/anagrafica/` | `GET /diari/{id}/anagrafica` |
| `PUT /api/diari/<pk>/modulo/anagrafica/` | `PUT /diari/{id}/anagrafica` |
| `GET /api/diari/<pk>/modulo/presentazione/` | `GET /diari/{id}/presentazione` |
| `PUT /api/diari/<pk>/modulo/presentazione/` | `PUT /diari/{id}/presentazione` |
| `GET /api/diari/<pk>/modulo/impresa/<n>/` | `GET /diari/{id}/imprese/{n}` |
| `PUT /api/diari/<pk>/modulo/impresa/<n>/` | `PUT /diari/{id}/imprese/{n}` |
| `GET /api/diari/<pk>/modulo/missione/` | `GET /diari/{id}/missione` |
| `PUT /api/diari/<pk>/modulo/missione/` | `PUT /diari/{id}/missione` |
| `GET /diari/<pk>/allegati/?modulo=` (JSON web) | `GET /diari/{id}/allegati?modulo=` |
| `POST /diari/<pk>/allegati/upload/` | `POST /diari/{id}/allegati` |
| `POST /diari/<pk>/allegati/<a>/elimina/` | `DELETE /diari/{id}/allegati/{a}` |
| `GET /diari/<pk>/allegati/<a>/preview/` | `GET /diari/{id}/allegati/{a}/anteprima` |

Stesse garanzie: optimistic locking con 409 e `server_version`, transizione automatica
NON_INIZIATO → IN_COMPILAZIONE al primo salvataggio, validazione con 400 `{error, errors}` per i
moduli; in più `Idempotency-Key`. Differenze: `PUT` senza `version` → 422 (prima 400
`version_required`); corpo non JSON → 422 (prima 400 `invalid_json`); upload non valido → 422 con
`errori` per campo (prima 400 `{error}`).
