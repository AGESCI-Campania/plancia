# Export riassuntivo diari

L'export riassuntivo genera un unico foglio con tutti i diari dell'edizione (o un sottoinsieme filtrato per ruolo), combinando anagrafica, moduli CSQ, relazione finale CRP e valutazione.

**URL:** `GET /edizioni/<pk>/export-diari/?formato=xlsx|ods|csv`

---

## Formati disponibili

| Formato | Content-Type | Note |
|---|---|---|
| `xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | Stile verde AGESCI; header freezati |
| `ods` | `application/vnd.oasis.opendocument.spreadsheet` | Compatibile con LibreOffice |
| `csv` | `text/csv; charset=utf-8-sig` | BOM UTF-8 per compatibilità Excel su Windows |

---

## Ruoli e visibilità

| Ruolo | Diari inclusi | Relazione finale | Valutazione |
|---|---|---|---|
| `incaricato_eg`, `admin`, `segreteria` | Tutti | Sì | Sì (se presente) |
| `crp` | Solo il proprio reparto | Sì | Solo se pubblicata |
| `csq` | Solo il proprio diario | No | Solo se pubblicata |

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
8. **Missione**: titolo, data, descrizione, posti d'azione (concat descrizione), esiti (concat)
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

La soglia è configurabile con la variabile d'ambiente `EXPORT_DIARI_SOGLIA_ASYNC` (default 50).

Quando l'export è asincrono, la view risponde con una pagina di conferma e invia l'export via email al richiedente al termine del task Celery.

---

## Configurazione

Variabili d'ambiente rilevanti:

```env
# Soglia diari oltre cui xlsx/ods diventano asincroni (default 50)
EXPORT_DIARI_SOGLIA_ASYNC=50
```

Il formato CSV è sempre sincrono e non è configurabile.

---

## Distinzione dall'export "Esiti"

| Export | URL | Contenuto | Formato |
|---|---|---|---|
| **Esiti** (M3, già esistente) | `/edizioni/<pk>/excel/visualizza/` | Solo esiti/voti per edizione | xlsx |
| **Diari** (M6, nuovo) | `/edizioni/<pk>/export-diari/?formato=…` | Tutti i campi dei diari | xlsx, ods, csv |

L'export Esiti è generato da `genera_excel_edizione()` in `apps/exports/service.py` ed è sempre sincrono.
L'export Diari usa `genera_export_diari()` con la soglia async.
