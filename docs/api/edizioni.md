# API Fase 2 — Edizioni, home, valutazioni, Google Drive

Prefisso `/api/v1`. Autenticazione come nel resto dell'API (cookie di sessione per la SPA,
`X-Session-Token` per l'app mobile); anonimo → `401`. Errori: `403` permesso negato,
`404` non trovato, `422` stato non valido o dati non validi (con `errori` per campo).
"Staff" = Admin, Segreteria, Incaricati EG (e superuser).

## Edizioni (`/edizioni`)

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/edizioni` | tutti | Elenco edizioni (invariato; campi opzionali aggiunti) |
| GET | `/edizioni/attiva` | tutti | Home: `riepilogo` dell'edizione aperta/in valutazione più recente (o `null`), `puo_gestire` |
| GET | `/edizioni/{id}` | tutti | Dettaglio edizione (invariato; campi opzionali aggiunti) |
| GET | `/edizioni/{id}/riepilogo` | tutti | Diari visibili al ruolo (totale, filtri zona/gruppo/specialità); conteggi per stato solo allo staff; `puo_gestire`, `puo_pubblicare_esiti` (Incaricato EG, Admin) |
| POST | `/edizioni` | staff | Crea edizione (validazione di `EdizioneForm`; `stato` predefinito `bozza`) → `201` |
| PATCH | `/edizioni/{id}` | staff | Modifica parziale dell'edizione |
| POST | `/edizioni/{id}/azioni/{azione}` | staff | `apri` · `avvia-valutazione` · `chiudi` (FSM bozza → aperta → in valutazione → chiusa) |
| GET | `/edizioni/{id}/dilazioni?diario_id=` | staff | Dilazioni concesse (paginato) |
| POST | `/edizioni/{id}/dilazioni` | staff | Concede una dilazione (`diario_id`, `nuova_scadenza`, `motivazione`); solo prima dell'invio del diario → `201` |
| POST | `/edizioni/{id}/pubblica-esiti?scadenza=prima\|seconda` | Incaricato EG, Admin | Pubblica tutti gli esiti confermati (`{"pubblicati": n}`) |
| GET | `/edizioni/{id}/esiti-excel` | staff | Scarica `Esiti_GV_<anno>.xlsx` |
| GET | `/edizioni/{id}/export-diari?formato=xlsx\|ods\|csv` | staff | Export riassuntivo diari: `200` con il file se i diari sono ≤ `EXPORT_DIARI_SOGLIA_ASYNC` (CSV sempre), altrimenti `202` `{detail, formato, diari}` e file via email |

## Valutazione (`/diari/{id}/...`)

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/diari/{id}/valutazione` | staff; Pattuglia GV assegnata; Capo Reparto del diario dopo la pubblicazione | Dettaglio con `azioni` proponibili al ruolo; mai al Capo Squadriglia; `404` se non c'è valutazione |
| GET | `/diari/{id}/valutazione/azioni` | come il dettaglio | Solo le `azioni` proponibili, anche quando la valutazione non esiste ancora (il dettaglio dà `404`): serve alla pagina per proporre la prima valutazione o l'assegnazione. Non crea nulla |
| POST | `/diari/{id}/valutazione/assegna-pgv` | Incaricato EG, Admin, Segreteria | Assegna un membro della Pattuglia GV (`pgv_pk`) |
| POST | `/diari/{id}/valutazione/valuta` | Incaricato EG, Admin, Segreteria | Valutazione diretta (anche da `inviato`, sovrascrive una proposta in revisione) |
| POST | `/diari/{id}/valutazione/proposta` | Pattuglia GV assegnata | Proposta Approvata/Non approvata (→ in revisione) |
| POST | `/diari/{id}/valutazione/conferma` | Incaricato EG, Admin | Conferma la proposta |
| POST | `/diari/{id}/valutazione/rigetta` | Incaricato EG, Admin | Rigetta la proposta (diario torna in valutazione) |
| POST | `/diari/{id}/valutazione/modifica` | Incaricato EG, Admin | Modifica l'esito fino alla pubblicazione |
| POST | `/diari/{id}/valutazione/pubblica` | Incaricato EG, Admin | Pubblica l'esito del diario |
| POST | `/diari/{id}/azioni/{csq-invia\|invia\|riapri}` | come `actions.py` | Transizioni FSM del diario (invariato) |

## Google Drive (`/drive`)

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| POST | `/drive/oauth` | staff | Corpo `{"edizione_id"?}` → `{"url"}` di autorizzazione Google (PKCE e state in sessione) |
| GET | `/drive/stato` | staff | `oauth_configurato` e account collegati (senza token) |
| GET | `/drive/cartelle?account=&q=&parent_id=` | staff | Picker: prime 20 cartelle dell'account (`[{id, nome}]`); con `parent_id` solo le sottocartelle di quella cartella |
| POST | `/drive/cartelle` | staff | Crea cartella (`account`, `nome`, `parent_id`?) → `201 {id, nome}` |
| GET | `/drive/cartelle/{folder_id}?account=` | staff | Nome e link della cartella |
| GET | `/drive/edizioni/{id}` | staff | Configurazione Drive dell'edizione (account, cartelle, formato, `cartelle_configurate`) |
| PUT | `/drive/edizioni/{id}` | staff | Salva cartella allegati/output e formato nome; quando sono tutti valorizzati la configurazione si blocca (poi `422`) |

Errori di Google → `502`.

**Callback OAuth**: resta la vista Django `GET /drive/oauth/callback/` (percorso registrato
presso Google). A fine flusso reindirizza alla SPA: `/edizioni/<id>?drive=ok|errore&messaggio=…`
se il flusso è partito da un'edizione, altrimenti `/impostazioni/drive?esito=ok|errore&messaggio=…`.
