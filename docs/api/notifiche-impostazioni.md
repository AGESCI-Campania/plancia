# API Fase 2 — Notifiche (inviti) e Impostazioni

Endpoint sotto `/api/v1/`. Ruoli: **Staff** = Admin, Segreteria, Incaricato EG (ruolo attivo;
il superuser passa sempre). Errori: 401 non autenticato, 403 permesso negato, 404 non trovato,
422 dati non validi (`errori` per campo) o azione non consentita. Le scritture con cookie di
sessione richiedono il token CSRF (`X-CSRFToken`), come il resto dell'API.

Logica condivisa con le viste web: `apps/notifications/service.py` e `apps/siteconfig/services.py`.

## Notifiche — `/notifiche`

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/notifiche/inviti/riepilogo` | Staff | Edizione attiva (la più recente aperta o in valutazione), contatori inviti (Capi Reparto deduplicati), zone e gruppi per i filtri, etichetta del backend massivo |
| GET | `/notifiche/inviti` | Staff | Un diario per riga: Capo Squadriglia, Capo Reparto, ultimo invito di ciascuno con stato e **stato di consegna** (`delivery_status`, `delivery_error`), id degli inviti reinviabili. Filtri `zona`, `gruppo`, `q` (nome/cognome). Paginato (`limit`, `offset`) |
| POST | `/notifiche/inviti/invia-edizione` | Staff | `{"tipo": "capi"\|"csq", "backend": "standard"\|"massivo"}` → 202, invio accodato (Celery) |
| POST | `/notifiche/diari/{diario_id}/inviti` | Staff | `{"ruoli": ["csq","crp"]}` → 202, inviti mancanti del diario accodati |
| GET | `/notifiche/inviti/miei` | Capo Reparto | Diari propri dell'edizione attiva con l'ultimo invito al Capo Squadriglia e `reinviabile` |
| POST | `/notifiche/inviti/{invito_id}/reinvia` | Staff; Capo Reparto solo per i Capi Squadriglia dei propri diari | Nuovo invito (stesso tipo), il precedente scade. 422 se già attivato |
| GET | `/notifiche/inviti/{token}` | **Pubblico** | Dati per la pagina di attivazione: tipo, ruolo, stato, `attivabile`, `richiede_codice_socio`, `messaggio` (se scaduto/già usato), squadriglia ed edizione. Nessun dato personale |
| POST | `/notifiche/inviti/{token}/attiva` | **Pubblico** (CSRF richiesto) | Corpo JSON (`{}` per gli inviti standard; `{"codice_socio", "email"}` per i Capi Squadriglia). Verifica scadenza/già usato, codice socio ed email (formato, non già registrata), aggiorna l'email, crea la Nomina mancante, attiva l'invito ed **effettua il login nella sessione** (cookie). Risposta: `detail`, `ruolo`, `diario_id` |

`{token}` è un UUID, `{invito_id}`/`{diario_id}` interi.

## Impostazioni — `/impostazioni`

| Metodo | Percorso | Ruoli | Descrizione |
|---|---|---|---|
| GET | `/impostazioni` | Staff | Tutte le sezioni (identità, footer con link, email, sicurezza, allegati, diagnostica) + `scelte` per i campi a scelta. Segreti mai restituiti: `smtp_password_impostato`, `email_provider_api_key_impostato`, `email_provider_webhook_secret_impostato`; `webhook_url` da configurare nel provider |
| PATCH | `/impostazioni/identita` | Staff | `titolo`, `sottotitolo` |
| PATCH | `/impostazioni/footer` | Staff | `footer_testo` (HTML) |
| PATCH | `/impostazioni/email` | Staff | Campi della sezione Posta elettronica; segreti vuoti/assenti = invariati; con Gmail OAuth attivo i campi SMTP manuali non vengono modificati. Stesse validazioni del form web |
| PATCH | `/impostazioni/sicurezza` | Staff | MFA ruoli estesi, parametri axes |
| PATCH | `/impostazioni/allegati` | Staff | `allegati_max_px` |
| PATCH | `/impostazioni/diagnostica` | Staff | `manutenzione`, `debug_toolbar`, `debug_diagnostico` |
| GET / PUT | `/impostazioni/manutenzione` | Staff | Stato / `{"attiva": bool}` (non esiste un campo "messaggio" in `Impostazioni`) |
| GET / POST | `/impostazioni/footer/link` | Staff | Elenco in ordine / crea (max 4; `tipo` dedotto `sito_web` se manca) |
| PATCH / DELETE | `/impostazioni/footer/link/{link_id}` | Staff | Modifica / elimina |
| POST | `/impostazioni/footer/link/ordina` | Staff | `{"ids": [...]}`: tutti gli id nel nuovo ordine |
| GET | `/impostazioni/pagine` | Staff | Pagine statiche (privacy, termini) |
| GET | `/impostazioni/pagine/{slug}` | **Pubblico** | Titolo e contenuto (pagina vuota di default se non ancora scritta) |
| PUT | `/impostazioni/pagine/{slug}` | Staff | `titolo`, `contenuto` |
| POST | `/impostazioni/pagine/{slug}/importa` | Staff | Carica il contenuto predefinito (`templates/siteconfig/default_pages/`) |
| GET | `/impostazioni/mail` | Staff | Tutte le chiavi dei template email, tag disponibili, se personalizzate |
| GET / PUT | `/impostazioni/mail/{chiave}` | Staff | Dettaglio (con `chiavi_senza_record` per la copia) / crea o modifica (`oggetto`, `corpo_html`, `attivo`) |
| DELETE | `/impostazioni/mail/{chiave}` | **Admin** | Elimina (torna il file predefinito) |
| POST | `/impostazioni/mail/{chiave}/importa` | Staff | Crea dal file `templates/mail/<chiave>.html` (422 se esiste già) |
| POST | `/impostazioni/mail/{chiave}/copia` | Staff | `{"target_chiave"}` verso una chiave non personalizzata |
| POST | `/impostazioni/immagini-mail` | Staff | Multipart `file` (JPEG/PNG/GIF/WebP, max 2 MB) → 201 `{"url"}` per l'editor |
| POST | `/impostazioni/email/test` | Staff | `{"backend": "smtp"\|"transazionale"}`: email di test al proprio indirizzo; 422 con il messaggio d'errore del backend |
| POST | `/impostazioni/email/gmail/oauth` | Staff | Avvia Gmail SMTP OAuth (PKCE, state in sessione) → `{"url"}` di consenso Google |
| POST | `/impostazioni/email/gmail/disconnetti` | Staff | Scollega l'account Gmail, disattiva OAuth |
| GET | `/impostazioni/log-export` | Staff | Log generazione PDF/Excel, paginato |
| GET | `/impostazioni/cache-pdf` | Staff | Edizioni con numero di PDF in cache, `generazione_in_corso` (lock) e `task_id` |
| GET | `/impostazioni/cache-pdf/file` | Staff | PDF in cache, filtro `edizione_id`, paginato |
| DELETE | `/impostazioni/cache-pdf/file/{file_id}` | Staff | Elimina un PDF dalla cache |
| POST | `/impostazioni/cache-pdf/invalida` | Staff | `{"edizione_id": int\|null}` (null = tutte) → `eliminati` |
| POST | `/impostazioni/cache-pdf/genera` | Staff | `{"edizione_id"}` → 202; lock atomico, 422 se già in corso |
| POST | `/impostazioni/cache-pdf/interrompi` | Staff | `{"edizione_id"}` → 202, interruzione dopo il diario in corso |
| GET | `/impostazioni/task/{task_id}` | Staff | Avanzamento task Celery: `stato`, `progresso`, `completati`, `totale` |
| GET | `/impostazioni/axes` | Staff | Ultimi 100 tentativi di accesso falliti |
| DELETE | `/impostazioni/axes/{attempt_id}` | **Admin** | Sblocca un IP |
| POST | `/impostazioni/axes/sblocca-tutti` | **Admin** | Sblocca tutti → `eliminati` |

### Callback Gmail SMTP OAuth

La callback resta la vista Django `/impostazioni/gmail-smtp/oauth/callback/` (registrata presso
Google). Se il flusso è partito dall'API rimanda alla SPA:
`/impostazioni/email?esito=ok|errore&messaggio=...`; se è partito dalla vecchia pagina Django
torna a quella (messaggi flash), finché le viste web esistono.
