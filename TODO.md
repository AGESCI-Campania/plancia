# TODO — Plancia v2.0: Offline-first PWA

## Obiettivo
Implementare una PWA offline-first che permetta al Capo Squadriglia di compilare
il Diario di Bordo senza connessione (tipicamente in campo/montagna) e sincronizzare
al ritorno della connettività.

---

## Decisioni architetturali

### Conflict resolution — Optimistic Locking (opzione B)
- Ogni modulo ha un campo `version` (intero incrementale).
- Il client invia la versione su cui ha basato la modifica.
- Il server rifiuta con errore esplicito se la versione non corrisponde.
- Nessuna perdita silenziosa di dati.
- **Lo stato del diario (FSM) appartiene sempre al server** — nessuna transizione di stato avviene offline.

### Allegati
- Due code separate: prima testi (veloci), poi allegati (binari pesanti).
- Resize delle immagini **client-side** prima di mettere in coda (anziché server-side).
- Progress visibile all'utente ("3 foto in attesa di sync").
- La coda allegati riprende dall'elemento successivo se la connessione cade a metà.

### Auth offline
- Se la sessione scade mentre si è offline, il service worker intercetta il 401.
- La coda **non viene scartata** — viene trattenuta con banner "hai modifiche in attesa, accedi per sincronizzare".
- Al login successivo il sync parte automaticamente.
- Allungare la durata della sessione per il ruolo CSQ (nessun MFA obbligatorio, profilo di rischio diverso da Admin/Incaricati).

---

## Piano di implementazione

| # | Fase | Stima |
|---|---|---|
| 1 | Setup branch `v2-offline` + ambiente staging + script anonimizzazione DB | 2–3 gg |
| 2 | API JSON moduli 1–5 (fondamento di tutto) | 8–10 gg |
| 3 | Optimistic locking (`version` sui moduli, conflict detection server-side) | 2–3 gg |
| 4 | Service worker + cache asset (app installabile, risorse statiche offline) | 3–4 gg |
| 5 | IndexedDB + salvataggio offline (intercettare submit, coda locale) | 8–10 gg |
| 6 | Background Sync testi (svuotare la coda al ritorno della connessione) | 4–5 gg |
| 7 | Auth: sync al login (gestire 401, banner, rilancio sync post-autenticazione) | 3–4 gg |
| 8 | Coda allegati (resize client-side, coda separata, progress UI) | 7–8 gg |
| 9 | Test su staging con dati realistici | 4–5 gg |
| 10 | Aggiornamento manuali (utente CSQ, admin, CLAUDE.md, README.md) | 3–4 gg |
| 11 | Merge main → branch, test regressione finale | 1–2 gg |
| 12 | PR → main, tag `v2.0.0`, deploy produzione | 1–2 gg |
| | **Totale stimato** | **45–58 gg** |

Circa **9–12 settimane** a tempo pieno.

Fasi più rischiose per stima: API JSON (complessità moduli + coverage) e Background Sync
(il debugging offline è lento). Lo script di anonimizzazione è piccolo ma delicato.

---

## Branch e staging

- Branch di sviluppo: `v2-offline`
- `main` continua a ricevere patch per la produzione durante lo sviluppo
- Mergiare `main → v2-offline` frequentemente (almeno a ogni release di produzione) per evitare conflitti accumulati
- Ambiente staging: `docker-compose.staging.yml` affiancato sulla stessa macchina, porte e dominio separati (es. `staging.agescicampania.org`)
- DB staging popolato con dump anonimizzato della produzione (mai dump grezzo — dati di minori)

---

## Procedura di release (v2.0.0)

1. Merge finale `main → v2-offline`, risolvere conflitti
2. Test completi su staging (FSM, PDF, Drive, offline, sync)
3. PR `v2-offline → main` con checklist:
   - [ ] Tutte le migrazioni testate su staging
   - [ ] Variabili d'ambiente nuove documentate in `.env.*.example`
   - [ ] Service worker: version bump (obbligatorio per forzare aggiornamento sui client)
   - [ ] Manuali aggiornati
4. Tag `v2.0.0`
5. Deploy produzione con procedura standard (CLAUDE.md) + svuotamento cache SW sui client

---

## Manuali da aggiornare

- `CLAUDE.md` — procedura staging, branch workflow
- `README.md` — stack aggiornato, istruzioni setup staging
- Manuale utente CSQ — installazione PWA, uso offline, banner "sync in attesa"
- Manuale admin — gestione staging, script anonimizzazione DB
