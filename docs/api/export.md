# Export riassuntivo diari

L'export riassuntivo genera un unico foglio con tutti i diari dell'edizione, combinando anagrafica, moduli del Capo Squadriglia, relazione finale del Capo Reparto e valutazione.

**URL:** `GET /api/v1/edizioni/{id}/export-diari?formato=xlsx|ods|csv` (default `xlsx`)

---

## Formati disponibili

| Formato | Content-Type | Note |
|---|---|---|
| `xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | Stile verde AGESCI; header freezati |
| `ods` | `application/vnd.oasis.opendocument.spreadsheet` | Compatibile con LibreOffice |
| `csv` | `text/csv; charset=utf-8-sig` | BOM UTF-8 per compatibilità Excel su Windows |

---

## Ruoli e visibilità

L'endpoint è riservato allo **staff** (`richiedi_staff`: Admin, Segreteria, Incaricati EG; 403
agli altri ruoli). Il foglio contiene tutti i diari dell'edizione, con relazione finale e
valutazione (se presente). `genera_export_diari()` filtra comunque le colonne in base al ruolo
di chi lo richiede.

---

## Colonne del foglio

Il foglio ha un'unica riga per diario. Le colonne sono nell'ordine:

1. **Identificazione**: zona, gruppo, reparto, squadriglia, edizione, tipo (Nuovo/Rinnovo), stato
2. **Anagrafica CRP**: nome, cognome, email, cellulare
3. **Anagrafica CSQ**: nome, cognome, email, cellulare
4. **Presentazione**: nome squadriglia, specialità squadriglia, testo presentazione, esiti specialità (concat)
5. **Membri**: lista concatenata `nome (ruolo, sentiero, spec_ind, brevetto)` separata da ` | `
6. **Impresa 1**: titolo, data inizio, data fine, perché, come, cosa abbiamo imparato, link, posti d'azione (concat `chi — cosa`), esiti (concat)
7. **Impresa 2**: stesse colonne (vuote se assente o tipo Rinnovo senza impresa 2)
8. **Missione**: titolo, data, descrizione
9. **Relazione finale** *(CRP — omessa per CSQ)*: sintesi impresa 1, sintesi impresa 2, sintesi missione, considerazioni CRP, specialità conquistata (Sì/No)
10. **Valutazione** *(solo se autorizzato e pubblicata)*: esito, note, pubblicata il
11. **Drive**: link cartella diario su Google Drive (se configurata)

---

## Comportamento asincrono

L'export può essere sincrono o asincrono in base alla dimensione:

| Condizione | Comportamento |
|---|---|
| CSV (qualsiasi dimensione) | Sempre sincrono — risposta immediata con file |
| xlsx/ods, diari ≤ `EXPORT_DIARI_SOGLIA_ASYNC` | Sincrono — risposta immediata con file |
| xlsx/ods, diari > `EXPORT_DIARI_SOGLIA_ASYNC` | Asincrono — risposta `202 Accepted`, file inviato via email |

La soglia è l'impostazione Django `EXPORT_DIARI_SOGLIA_ASYNC` in `config/settings/base.py`
(fissa a 50, non letta dall'ambiente).

Quando l'export è asincrono l'API risponde `202` con
`{"detail": "...", "formato": "xlsx", "diari": N}` e invia l'export via email al richiedente al
termine del task Celery.

---

## Distinzione dall'export "Esiti"

| Export | URL | Contenuto | Formato |
|---|---|---|---|
| **Esiti** | `GET /api/v1/edizioni/{id}/esiti-excel` | Solo esiti/voti per edizione | xlsx |
| **Diari** | `GET /api/v1/edizioni/{id}/export-diari?formato=…` | Tutti i campi dei diari | xlsx, ods, csv |

L'export Esiti è generato da `genera_excel_edizione()` in `apps/exports/service.py` ed è sempre sincrono.
L'export Diari usa `genera_export_diari()` con la soglia async.
