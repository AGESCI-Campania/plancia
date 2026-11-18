# API REST Plancia — Indice degli endpoint

Tutti gli endpoint sono sotto `/api/v1/`; autenticazione richiesta tranne dove indicato
(`/app-status`, `/sito`, `GET /impostazioni/pagine/{slug}`, lettura e attivazione degli inviti). Per autenticazione, ruoli, rate limiting e
gestione degli errori vedi [`overview.md`](overview.md).

Il riferimento completo e sempre aggiornato è lo schema **OpenAPI** generato da django-ninja:
`/api/v1/docs` (Swagger, con login) e `/api/v1/openapi.json`; la SPA ne ricava i tipi con
`npm run api:tipi`. Qui sotto la descrizione per dominio, con ruoli e regole.

| Dominio | Documento | Prefissi |
|---|---|---|
| Profilo, utenti, nomine, impersonazione, soci | [utenti.md](utenti.md) | `/me`, `/utenti`, `/org` |
| Edizioni, home, valutazioni, Google Drive | [edizioni.md](edizioni.md) | `/edizioni`, `/diari/{id}/valutazione`, `/drive` |
| Diari, moduli 1–6, allegati, PDF, referenti | [diari.md](diari.md) | `/diari` |
| Inviti e impostazioni | [notifiche-impostazioni.md](notifiche-impostazioni.md) | `/notifiche`, `/impostazioni` |
| Importazioni | [importazioni.md](importazioni.md) | `/importazioni` |
| Helpdesk | [helpdesk.md](helpdesk.md) | `/helpdesk` |
| Statistiche | [statistiche.md](statistiche.md) | `/statistiche` |
| Dati pubblici del sito e versione | [sito.md](sito.md) | `/sito` |
| Aggiornamenti del server (solo Admin) | [aggiornamenti.md](aggiornamenti.md) | `/aggiornamenti` |
| Export riassuntivo dei diari | [export.md](export.md) | `/edizioni/{id}/export-diari` |
| Compatibilità dell'app mobile | — | `/app-status` |

Autenticazione: allauth headless sotto `/_allauth/browser/v1/` (SPA, cookie di sessione + CSRF)
e `/_allauth/app/v1/` (app mobile, header `X-Session-Token`). Gli endpoint PWA 2.x `/api/diari/…`
e `/api/soci/` sono stati rimossi in 3.0 (mappa in [diari.md](diari.md)).
