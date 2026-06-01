# Manuale d'uso — Plancia

**Piattaforma Guidoncini Verdi · AGESCI Campania**

Plancia è la piattaforma web per la gestione del concorso Guidoncini Verdi della Branca E/G.
Permette alle squadriglie di compilare il Diario di Bordo, ai Capi Reparto di integrarlo, ai
Pattugliatori di valutarlo e alla Segreteria di amministrare l'intera edizione.

---

## Guida per ruolo

| Ruolo | Funzione principale |
|---|---|
| [Capo Squadriglia (CSQ)](csq.md) | Compila i moduli del Diario di Bordo |
| [Capo Reparto / CRP](crp.md) | Integra il diario con la Relazione finale |
| [Pattuglia GV (PGV)](pgv.md) | Valuta i diari assegnati |
| [Incaricato EG](incaricato.md) | Supervisiona le valutazioni e pubblica gli esiti |
| [Segreteria](segreteria.md) | Gestisce utenti, edizioni e import |
| [Amministratore](admin.md) | Configura la piattaforma, OAuth e autenticazione social |

---

## Struttura del Diario di Bordo

Il Diario è composto da sei moduli, compilati in ordine:

| Modulo | Titolo | Chi compila |
|---|---|---|
| 1 | Anagrafica | CSQ / CRP |
| 2 | Presentazione squadriglia | CSQ |
| 3 | 1ª Impresa | CSQ |
| 4 | 2ª Impresa *(Rinnovo: facoltativo)* | CSQ |
| 5 | Missione | CSQ |
| 6 | Relazione finale CRP | CRP *(mai visibile al CSQ)* |

---

## Accesso alla piattaforma

L'URL della piattaforma viene comunicato dalla Segreteria regionale.
Si accede con email e password ricevuti via invito, oppure con i pulsanti
**Accedi con Google / Microsoft / Apple** se configurati dall'Admin.

Gli utenti con ruolo Admin, Segreteria o Incaricato EG devono configurare
l'**autenticazione a due fattori (MFA)** al primo accesso tramite un'app
authenticator (Google Authenticator, Aegis, ecc.).

---

## Note sulla modalità offline (PWA)

Plancia funziona anche senza connessione. Se vai offline mentre compili un modulo:

- I dati inseriti vengono **salvati automaticamente** nel browser.
- Le foto selezionate vengono **accodate localmente**.
- Quando la connessione viene ripristinata, tutto viene sincronizzato in automatico.

Un banner colorato in basso alla pagina segnala lo stato della connessione.
