# API REST Plancia — Riferimento Endpoint

Tutti gli endpoint sono sotto `/api/v1/`. Autenticazione richiesta su tutti.  
Per autenticazione e gestione errori vedi [`overview.md`](overview.md).

---

## /me

### GET /me

Restituisce l'utente autenticato corrente.

**Risposta 200:**
```json
{
  "pk": 1,
  "email": "mario.rossi@esempio.it",
  "nome": "Mario",
  "cognome": "Rossi",
  "ruolo": "csq",
  "ruolo_display": "Capo Squadriglia"
}
```

---

## /edizioni

### GET /edizioni

Lista delle edizioni (anno scolastico Guidoncini Verdi).

**Risposta 200:**
```json
[
  {
    "pk": 3,
    "nome": "2024-2025",
    "stato": "aperta",
    "stato_display": "Aperta",
    "scadenza_1": "2025-03-31",
    "scadenza_2": "2025-05-31"
  }
]
```

### GET /edizioni/{pk}

Dettaglio singola edizione.

---

## /org

### GET /org/albero

Struttura organizzativa completa (zone → gruppi → reparti → squadriglie).

**Risposta 200:**
```json
[
  {
    "pk": 1,
    "nome": "Napoli",
    "gruppi": [
      {
        "pk": 5,
        "nome": "Napoli 1",
        "reparti": [
          {
            "pk": 12,
            "nome": "Reparto Aquile",
            "squadriglie": [
              {"pk": 34, "nome": "Aquile"}
            ]
          }
        ]
      }
    ]
  }
]
```

---

## /diari

### GET /diari

Lista diari visibili all'utente autenticato (filtrata per ruolo).

**Query parameters:**

| Parametro | Tipo | Descrizione |
|---|---|---|
| `edizione` | int | Filtra per edizione pk |
| `stato` | string | Filtra per stato FSM |
| `squadriglia` | int | Filtra per squadriglia pk |
| `page` | int | Numero pagina (default 1) |

**Risposta 200:**
```json
{
  "count": 15,
  "next": null,
  "previous": null,
  "items": [
    {
      "pk": 42,
      "squadriglia": {"pk": 34, "nome": "Aquile"},
      "edizione": {"pk": 3, "nome": "2024-2025"},
      "tipo": "nuovo",
      "tipo_display": "Nuovo",
      "stato": "in_compilazione",
      "stato_display": "In compilazione",
      "pubblicato": false,
      "version": 7
    }
  ]
}
```

### GET /diari/{pk}

Dettaglio completo diario con tutti i moduli compilati.

**Risposta 200** (campi visibili variano per ruolo):
```json
{
  "pk": 42,
  "squadriglia": {"pk": 34, "nome": "Aquile"},
  "edizione": {"pk": 3, "nome": "2024-2025"},
  "tipo": "nuovo",
  "stato": "in_compilazione",
  "pubblicato": false,
  "anagrafica": {
    "version": 2,
    "data": {
      "specialita": "ALPINISMO",
      "tipo_diario": "nuovo",
      "nome_csq": "Mario",
      "cognome_csq": "Rossi",
      "email_csq": "mario@esempio.it",
      "nome_crp": "Anna",
      "cognome_crp": "Bianchi",
      "email_crp": "anna@esempio.it",
      "membri": [
        {"nome": "Luigi Verdi", "ruolo": "", "sentiero": "partenza", "specialita_ind": "", "brevetto": ""}
      ]
    }
  },
  "presentazione": {
    "version": 1,
    "data": {
      "nome_squadriglia": "Aquile",
      "specialita_squadriglia": "ALPINISMO",
      "testo_presentazione": "La nostra squadriglia...",
      "esiti_specialita": []
    }
  },
  "imprese": [
    {
      "version": 3,
      "data": {
        "numero": 1,
        "titolo": "Uscita sul Vesuvio",
        "data_inizio": "2024-11-10",
        "data_fine": "2024-11-10",
        "perche": "...",
        "come": "...",
        "cosa_abbiamo_imparato": "...",
        "link_approfondimento": "",
        "posti_azione": [{"chi": "Mario Rossi", "cosa": "Ha cucinato"}],
        "esiti": []
      }
    }
  ],
  "missione": null,
  "relazione_finale": null,
  "valutazione": null
}
```

`relazione_finale` è `null` per i Capi Squadriglia (mai visibile).  
`valutazione` è `null` se non pubblicata (per CSQ/CRP) o se non ancora creata.

---

## /diari — Write (moduli)

### PUT /diari/{pk}/anagrafica

Aggiorna l'anagrafica della squadriglia (modulo 1).

**Permessi:** CSQ del diario, staff. Stato richiesto: `non_iniziato` o `in_compilazione`.

**Body:**
```json
{
  "version": 2,
  "data": {
    "specialita": "ALPINISMO",
    "tipo_diario": "nuovo",
    "nome_csq": "Mario",
    "cognome_csq": "Rossi",
    "email_csq": "mario@esempio.it",
    "cell_csq": "3331234567",
    "nome_crp": "Anna",
    "cognome_crp": "Bianchi",
    "email_crp": "anna@esempio.it",
    "cell_crp": "3339876543",
    "membri": [
      {
        "nome": "Luigi Verdi",
        "ruolo": "vice",
        "sentiero": "partenza",
        "specialita_ind": "",
        "brevetto": ""
      }
    ]
  }
}
```

**Risposta 200:**
```json
{
  "version": 3,
  "data": { "...": "..." }
}
```

**Errori:**
- `400` — dati non validi: `{"error": "validation", "errors": {"email_csq": ["indirizzo email non valido"]}}`
- `409` — conflitto versione: `{"error": "conflict", "server_version": 4}`

### PUT /diari/{pk}/presentazione

Aggiorna la presentazione (modulo 2). Stesso pattern di `/anagrafica`.

**Campi `data`:** `nome_squadriglia`, `specialita_squadriglia`, `testo_presentazione`, `esiti_specialita` (lista).

### PUT /diari/{pk}/imprese/{numero}

Aggiorna un'impresa (modulo 3 = impresa 1, modulo 4 = impresa 2). `numero` ∈ `{1, 2}`.

**Permessi aggiuntivi:** impresa 2 è opzionale per tipo `rinnovo`.

**Campi `data`:** `titolo`, `data_inizio`, `data_fine`, `perche`, `come`, `cosa_abbiamo_imparato`, `link_approfondimento`, `posti_azione` (lista `{chi, cosa}`), `esiti` (lista).

### PUT /diari/{pk}/missione

Aggiorna la missione (modulo 5). Stesso pattern.

**Campi `data`:** `titolo`, `data`, `descrizione`, `posti_azione_missione` (lista `{descrizione}`), `esiti` (lista).

### PUT /diari/{pk}/relazione-finale

Aggiorna la relazione finale CRP (modulo 6). **Senza optimistic locking.**

**Permessi:** CRP del diario, staff. Stato richiesto: `relazione_finale`.

**Body:**
```json
{
  "data": {
    "sintesi_impresa1": "...",
    "sintesi_impresa2": "...",
    "sintesi_missione": "...",
    "considerazioni": "...",
    "specialita_conquistata": true
  }
}
```

**Risposta 200:** `{"data": {...}}`

---

## /diari — Transizioni FSM

### POST /diari/{pk}/azioni/{azione}

Esegue una transizione di stato sul diario.

**Valori `azione`:** `csq-invia`, `invia`, `riapri`

| Azione | Da stato | A stato | Permesso |
|---|---|---|---|
| `csq-invia` | `in_compilazione` | `relazione_finale` | CSQ del diario |
| `invia` | `relazione_finale` | `inviato` | CRP del diario |
| `riapri` | `non_approvato` / `maggiori_info` | `in_compilazione` | Solo staff |

**Body:** vuoto (nessun payload richiesto).

**Risposta 200:**
```json
{
  "stato": "relazione_finale",
  "stato_display": "Relazione finale"
}
```

**Errori:**
- `403` — permesso negato: `{"detail": "Solo il Capo Squadriglia del diario può inviare la propria parte."}`
- `422` — stato non valido: `{"detail": "Il diario deve essere in compilazione."}`

---

## /diari — Valutazione

### GET /diari/{pk}/valutazione

Dettaglio valutazione del diario.

**Visibilità:**
- CSQ/CRP: solo se pubblicata
- PGV: solo se assegnato
- Staff/Incaricato/Admin: sempre

**Risposta 200:**
```json
{
  "esito": "approvato",
  "esito_display": "Approvato",
  "stato": "confermata",
  "note": "Ottimo lavoro.",
  "pubblicata": true,
  "assegnazioni": [
    {
      "pgv_pk": 99,
      "pgv_nome": "Giulia Neri",
      "pgv_email": "giulia@esempio.it"
    }
  ]
}
```

### POST /diari/{pk}/valutazione/assegna-pgv

Assegna un membro PGV al diario. **Solo staff/incaricato.**

**Body:** `{"pgv_pk": 99}`

**Risposta 200:** oggetto `ValutazioneApiSchema` aggiornato.

### POST /diari/{pk}/valutazione/valuta

Valuta direttamente (esito definitivo, senza passare per PGV). **Solo incaricato/admin/segreteria.**

**Body:** `{"esito": "approvato", "note": "..."}`

**Valori `esito`:** `approvato`, `non_approvato`, `maggiori_info`

### POST /diari/{pk}/valutazione/proposta

Propone valutazione (PGV). **Solo PGV assegnato al diario.**

**Body:** `{"esito": "approvato", "note": "..."}` — `maggiori_info` non è consentito dalla PGV.

### POST /diari/{pk}/valutazione/conferma

Conferma la proposta PGV. **Solo incaricato/admin.** Stato valutazione richiesto: `in_revisione`.

**Body:** `{"note": "..."}` (opzionale)

### POST /diari/{pk}/valutazione/rigetta

Rigetta la proposta PGV. **Solo incaricato/admin.** Il diario torna in `in_valutazione`.

**Body:** vuoto.

### POST /diari/{pk}/valutazione/modifica

Modifica l'esito prima della pubblicazione. **Solo incaricato/admin.** Non applicabile se già pubblicato.

**Body:** `{"esito": "non_approvato", "note": "..."}`

### POST /diari/{pk}/valutazione/pubblica

Pubblica l'esito del singolo diario. **Solo incaricato/admin.**

**Body:** vuoto.

**Risposta 200:** `{"stato": "...", "stato_display": "..."}`
