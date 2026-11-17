# API Fase 2 — utenti, profilo, ruoli, sessioni, impersonazione, soci

Prefisso `/api/v1`. Autenticazione: cookie di sessione (SPA, con `X-CSRFToken` sulle richieste
non GET) o `X-Session-Token` (app). Errori: `401` non autenticato, `403` permesso negato,
`404` non trovato, `422` dati non validi (`{"detail", "errori": {campo: [...]}}`).
"Staff" = Admin, Segreteria, Incaricato EG (o superutente).

Regole: `apps/accounts/services.py` (profilo, ruolo attivo, sessioni, creazione utenti, revoca,
impersonazione, menu), `apps/accounts/roles.py` (nomina, `ROLE_CREATABLE_BY`, categoria,
esclusività Capo Squadriglia, `can_hijack`), `apps/org/services.py` (ricerca soci).

## Utente corrente (`/me`)

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/me` | tutti | Campi storici (`id`, `email`, `nome_completo`, `ruolo`, `ruoli_attivi`, `is_staff_plancia`, `is_superuser`) + `first_name`, `last_name`, `socio` (codice, nome, cognome, categoria, gruppo, zona), `mfa_attiva`, `mfa_richiesta` (`ruolo_richiede_mfa`), `mfa_da_configurare` (stesse esenzioni del middleware MFA), `menu` (flag della sidebar), `impersonato_da`, `puo_modificare_email` |
| PATCH | `/me` | autenticato | Campi facoltativi: `email` (solo Capo Squadriglia: aggiorna anche il Socio; unicità, formato), `first_name`/`last_name` (solo utenti senza Socio, `puo_modificare_nome`; nome obbligatorio) |
| GET | `/me/profilo` | tutti | Pagina profilo: `utente` (come `/me`), `nomine`, ultimi 10 `accessi`, `social_accounts` collegati (lo scollegamento è in allauth headless) |
| GET | `/me/nomine` | tutti | Storico delle proprie nomine (anche revocate/scadute) |
| GET | `/me/avatar` | tutti | La propria immagine del profilo (da Sestante), inline; `404` se non c'è. `/me` la indica in `avatar_url` (con `?v=` dall'hash, per la cache) |
| GET | `/me/accessi` | tutti | Propri `LoginEvent`, paginati (`limit`, `offset`) |
| POST | `/me/ruolo` | tutti | `{"ruolo"}`: cambia il ruolo attivo (solo tra i ruoli attivi non scaduti); risponde come `/me` |
| GET | `/me/sessioni` | tutti | Sessioni allauth attive (`corrente` = questa) |
| POST | `/me/sessioni/termina-altre` | tutti | Termina tutte le altre sessioni (`UserSession.end()`); `{"terminate", "detail"}` |
| POST | `/me/impersonazione/termina` | utente impersonato | Come `hijack:release` (segnale `hijack_ended`); risponde come `/me` dell'operatore. Solo cookie di sessione |

Flag `menu`: `puo_vedere_diari`, `puo_gestire_edizioni`, `puo_vedere_utenti`, `puo_gestire_inviti`,
`puo_gestire_inviti_crp`, `puo_importare`, `puo_vedere_statistiche` (Admin, Incaricato EG),
`puo_vedere_impostazioni` (Admin), `puo_vedere_helpdesk`, `puo_gestire_helpdesk` (staff),
`puo_usare_admin_django` (Admin). Servono solo all'interfaccia.

## Gestione utenti (`/utenti`)

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/utenti` | staff | Lista paginata; filtri `ruolo` (attivo) e `q` (email, nome o cognome del socio) |
| GET | `/utenti/opzioni` | staff | Ruoli per i form: `ruoli`, `ruoli_nominabili`, `ruoli_nominabili_da_socio` (senza Capo Squadriglia), `ruoli_staff_creabili`, `puo_impersonare` |
| GET | `/utenti/{id}` | staff | Dettaglio: socio, ruoli attivi, `nomine` (storico completo con `attiva`/`scaduta`/`da_sso`), ultimi 20 `accessi`, `ruoli_nominabili`, `puo_impersonare` (per questo utente), `avatar_url` |
| GET | `/utenti/{id}/avatar` | staff | Immagine del profilo dell'utente, inline; `404` se non c'è |
| POST | `/utenti/staff` | staff (Admin crea Admin/Segreteria/Incaricato; Segreteria crea Incaricato) | `{"email", "first_name", "last_name", "ruolo"}`: utente senza Socio (`nomina_staff_diretto`) + mail per impostare la password; `201` |
| POST | `/utenti/da-socio` | staff | `{"socio_id", "ruolo"}`: account per un Socio capo + nomina; `201` |
| PATCH | `/utenti/{id}` | Admin, Segreteria (`roles.puo_modificare_nome_di`) | `{"first_name", "last_name"?}`: nome e cognome di un utente senza Socio; la Segreteria non modifica chi ha una nomina Admin. Risponde come `GET /utenti/{id}` (che espone `puo_modificare_nome`) |
| POST | `/utenti/{id}/nomine` | staff, secondo `ROLE_CREATABLE_BY` | `{"ruolo", "edizione_id"?, "scadenza"?}` (`roles.nomina`); `201` |
| POST | `/utenti/{id}/nomine/{nomina_id}/revoca` | staff, secondo `ROLE_CREATABLE_BY` | `attiva=False` (resta nello storico). Non si revocano nomine proprie né derivate da Sestante; se era il ruolo attivo l'utente passa al ruolo rimasto di rango più alto |
| POST | `/utenti/{id}/impersona` | Admin, Segreteria (`can_hijack`) | Come `hijack:acquire` (segnale `hijack_started`, `hijack_history` in sessione); risponde come `/me` dell'utente impersonato. Solo cookie di sessione (`422` con `X-Session-Token`): il login ruota sessione e token CSRF, la SPA deve rileggere il cookie `csrftoken` |

## Anagrafica (`/org`)

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/org/soci` | staff; Capo Reparto (solo ragazzi) | Autocompletamento Socio, max 20: `q` (nome, cognome, zona, gruppo, inizio codice), `categoria`, `ruolo` (ruolo attivo dell'utente collegato). Ogni voce: `id`, `user_pk`, `codice_socio`, `categoria`, `nome`, `cognome`, `gruppo`, `zona`, `label` |
