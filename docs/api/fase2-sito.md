# API Fase 2 — Sito pubblico

Router `apps/api/routers/sito.py` (`auth=None`), dati da `apps/siteconfig/sito.py` (usato anche
dal context processor `impostazioni`) e `apps/siteconfig/versione.py`. Raggiungibile prima del
login e **anche con la manutenzione attiva** (bypass in `MaintenanceModeMiddleware`).

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/api/v1/sito` | pubblico | Titolo, sottotitolo, `versione`, `commit`, `footer`, `pagine`, `manutenzione`, `login` |
| GET | `/api/v1/sito/pagine/{slug}` | pubblico | Pagina statica `privacy` o `termini` (`titolo`, `contenuto` HTML, `aggiornato_at`; segnaposto se mai salvata); 404 per altri slug |

Risposta di `GET /sito`:

- `versione`: versione del server da `pyproject.toml` (`versione_installata()`, in cache per
  processo); da confrontare con `__VERSIONE_APP__` della PWA. `/app-status` resta invariato.
- `footer`: `testo` (HTML, `Impostazioni.footer_testo` reso come template con `titolo`,
  `sottotitolo`, `versione`, `commit`), `links[] {tipo, url, etichetta}` (`FooterLink`),
  `manuale_url`.
- `pagine[] {slug, titolo}`: privacy e termini.
- `manutenzione {attiva, messaggio}`: il messaggio è `Impostazioni.manutenzione_messaggio` o il
  predefinito; vuoto se non attiva.
- `login {locale, provider[] {id, nome}}`: provider social/SSO configurati (solo quelli con
  client id, come la pagina di login). `id` va passato come `provider` a
  `POST /_allauth/browser/v1/auth/provider/redirect` (`google`, `microsoft`, `apple`, `sestante`).

Con la manutenzione attiva gli altri endpoint `/api/v1/` rispondono ai non superuser
`503 {"detail": "<messaggio>", "maintenance": true}` (prima mancava `maintenance`).
Comando `manage.py manutenzione`: vedi `fase2-aggiornamenti.md`.
