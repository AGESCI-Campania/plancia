# API REST Plancia — Panoramica

Base URL: `/api/v1/`  
Schema interattivo (Swagger UI): `/api/v1/docs`  
Schema OpenAPI JSON: `/api/v1/openapi.json`

---

## Autenticazione

L'API supporta due modalità di autenticazione, equivalenti per funzionalità:

### 1. Sessione web (cookie)

Esegui login tramite l'interfaccia web o tramite `/_allauth/browser/v1/auth/login` (allauth headless).
Il cookie di sessione Django viene inviato automaticamente dal browser.

```
POST /_allauth/browser/v1/auth/login
Content-Type: application/json

{"login": "utente@esempio.it", "password": "..."}
```

### 2. Token di sessione (X-Session-Token)

Per client mobile o API-only, usa allauth headless in modalità *app*:

```
POST /_allauth/app/v1/auth/login
Content-Type: application/json

{"login": "utente@esempio.it", "password": "..."}
```

La risposta contiene `meta.session_token`. Includi il token in ogni richiesta:

```
GET /api/v1/me
X-Session-Token: <token>
```

Il token è valido finché la sessione Django non scade (configurazione `SESSION_COOKIE_AGE`).

### MFA

Se l'utente ha MFA attivo, il login risponde con `401` e `meta.is_authenticated: false`.
Completa il secondo fattore:

```
POST /_allauth/app/v1/auth/2fa/authenticate
Content-Type: application/json
X-Session-Token: <token-provvisorio>

{"code": "123456"}
```

---

## Ruoli e visibilità

| Ruolo | Cosa può vedere/fare tramite API |
|---|---|
| `csq` (Capo Squadriglia) | Solo il proprio diario (moduli 1–5); valutazione solo se pubblicata |
| `crp` (Capo Reparto) | I diari del proprio reparto; relazione finale |
| `pgv` (Pattuglia GV) | Solo i diari assegnati; può proporre valutazione |
| `incaricato_eg` | Tutti i diari; tutte le azioni di valutazione |
| `segreteria` | Tutti i diari; tutte le azioni (eccetto conferma proposta PGV) |
| `admin` | Accesso completo |

La relazione finale (modulo 6) **non è mai visibile** al Capo Squadriglia.  
La valutazione **non è visibile** al Capo Squadriglia finché non pubblicata.

---

## Paginazione

Gli endpoint di lista restituiscono:

```json
{
  "count": 42,
  "next": "/api/v1/diari?page=2",
  "previous": null,
  "items": [...]
}
```

Parametro `page` (default 1), dimensione pagina configurabile via `?page_size=N` (max 100).

---

## Rate limiting

Le chiamate a `/api/v1/` sono soggette a rate limiting basato su Redis (fixed window).  
Il client è identificato tramite `X-Session-Token` (se presente) o indirizzo IP.

I limiti sono configurabili in **Impostazioni → API** da Admin/Segreteria:

| Parametro | Default |
|---|---|
| Max richieste al minuto | 60 |
| Max richieste all'ora | 1000 |

Quando il limite viene superato la risposta è `429 Too Many Requests` con header `Retry-After`:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 23
Content-Type: application/json

{"detail": "Troppe richieste. Riprova tra 23 secondi.", "retry_after": 23}
```

Il rate limiting può essere disabilitato globalmente da Impostazioni (`api_ratelimit_abilitato = false`).

---

## App version control

Ogni chiamata a `/api/v1/` può includere l'header `X-App-Version` con la versione dell'app mobile:

```
GET /api/v1/me
X-Session-Token: <token>
X-App-Version: 1.2.0
```

Il server risponde con comportamenti diversi in base alla versione configurata in Impostazioni:

| Condizione | Risposta |
|---|---|
| Versione ≥ `app_versione_minima` e ≥ `app_versione_deprecata` | Normale |
| Versione ≥ `app_versione_minima` ma < `app_versione_deprecata` | Normale + header `X-App-Upgrade-Warning: true` |
| Versione < `app_versione_minima` | `426 Upgrade Required` (blocco hard) |
| Header assente | Nessuna azione (client browser) |

Risposta `426`:
```json
{
  "detail": "Versione app non supportata. Aggiorna l'app per continuare.",
  "upgrade_required": true,
  "versione_minima": "2.0.0"
}
```

Per controllare la compatibilità al lancio dell'app senza autenticazione, usa `GET /api/v1/app-status`
(vedi [`endpoints.md`](endpoints.md)).

---

## Gestione errori

| HTTP | Significato | Struttura risposta |
|---|---|---|
| `400` | Dati non validi | `{"error": "validation", "errors": {campo: [msg]}}` |
| `401` | Non autenticato | `{"detail": "..."}` |
| `403` | Permesso negato | `{"detail": "..."}` |
| `404` | Risorsa non trovata | `{"detail": "..."}` |
| `409` | Conflitto versione (optimistic lock) | `{"error": "conflict", "server_version": N}` |
| `422` | Stato non valido per l'azione | `{"detail": "..."}` |
| `426` | Versione app non supportata | `{"detail": "...", "upgrade_required": true, "versione_minima": "..."}` |
| `429` | Rate limit superato | `{"detail": "...", "retry_after": N}` |
| `503` | Manutenzione | `{"detail": "Servizio in manutenzione", "maintenance": true}` |

### Optimistic locking (moduli write)

I moduli 1–5 hanno un campo `version`. Per aggiornare un modulo:

1. `GET /api/v1/diari/{id}` → leggi `anagrafica.version` (o `presentazione.version`, ecc.)
2. `PUT /api/v1/diari/{id}/anagrafica` con body `{"version": N, "data": {...}}`
3. Se nel frattempo qualcun altro ha salvato → `409 Conflict` con `server_version`
4. Ricarica, mostra conflitto all'utente, riprova

La relazione finale **non ha** optimistic locking (campo `version` assente).

---

## Versioning

L'API è versionata nel path (`/api/v1/`). Breaking changes richiedono una nuova versione major.
La versione corrente è `1.0.0` (campo `info.version` nello schema OpenAPI).

---

## CORS

In produzione, le origini autorizzate si configurano con la variabile d'ambiente `CORS_ALLOWED_ORIGINS`
(lista separata da virgola). `CORS_ALLOW_CREDENTIALS = True` è necessario per i cookie di sessione.
L'header `X-Session-Token` è nella whitelist CORS.
