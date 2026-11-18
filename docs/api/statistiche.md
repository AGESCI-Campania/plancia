# API Fase 2 — Statistiche

Router `apps/api/routers/statistiche.py`, calcoli in `apps/stats/services.py`. Ruoli: **Admin,
Segreteria, Incaricati EG** (anche la voce di menu, `puo_vedere_statistiche`); gli altri 403,
anonimo 401.

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/api/v1/statistiche?edizione_id=` | staff | `{edizioni, edizione, per_zona, globali, ticket}`: senza `edizione_id` l'edizione aperta/in valutazione più recente (o l'ultima) |

- `per_zona[]`: `zona {id, nome}`, `totale`, `approvati`, `non_approvati` (esiti pubblicati),
  `maggiori_info`, `pubblicati`, `percentuale_approvati` (solo zone con diari).
- `globali`: `totale`, `inviati`, `approvati`, `non_approvati`, `in_compilazione`, `pubblicati`.
- `ticket`: `totale`, `aperti`, `chiusi`, `per_categoria[] {chiave, categoria, count}` (ticket
  collegati a diari dell'edizione).

Sono dati grezzi: i grafici li disegna la SPA. Senza edizioni `edizione`, `globali` e `ticket`
sono `null`.
