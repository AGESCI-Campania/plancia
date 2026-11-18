# API Fase 2 — Helpdesk

Router `apps/api/routers/helpdesk.py`, regole in `apps/helpdesk/services.py`. Ogni utente autenticato apre ticket e vede **solo i propri**;
**Admin, Segreteria e Incaricati EG** (staff) vedono e gestiscono tutti i ticket. Anonimo 401.

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/api/v1/helpdesk/opzioni` | tutti | Categorie, stati, diari collegabili (propri per il Capo Squadriglia, dei suoi reparti per il Capo Reparto, nessuno per gli altri), `staff` |
| GET | `/api/v1/helpdesk` | tutti | Ticket visibili, paginati (`limit`, `offset`, filtro `stato`) |
| POST | `/api/v1/helpdesk` | tutti | `{oggetto, corpo, categoria, diario_id?}` → 201 dettaglio; 422 per campi non validi o diario non collegabile |
| GET | `/api/v1/helpdesk/{id}` | autore o staff | Dettaglio con risposte e `azioni` consentite (`rispondi`, `prendi_in_carico`, `chiudi`); 403 se di altri |
| POST | `/api/v1/helpdesk/{id}/risposte` | autore o staff | `{testo}` → 201; se risponde lo staff a un ticket aperto, passa in lavorazione |
| POST | `/api/v1/helpdesk/{id}/prendi-in-carico` | staff | Ticket in lavorazione, assegnato a chi lo prende |
| POST | `/api/v1/helpdesk/{id}/chiudi` | autore o staff | Chiude il ticket |

Su un ticket chiuso risposte, presa in carico e chiusura rispondono 422 (prima il blocco era
solo nell'interfaccia).
