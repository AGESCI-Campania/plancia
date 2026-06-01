# Manuale d'uso — Plancia

**Piattaforma Guidoncini Verdi · AGESCI Campania**

Plancia è la piattaforma web per la gestione del concorso Guidoncini Verdi della Branca E/G.
Permette alle squadriglie di compilare il Diario di Bordo, ai Capi Reparto di integrarlo, alla
Pattuglia Guidoncini Verdi di valutarlo e alla Segreteria di amministrare l'intera edizione.

---

## Guida per ruolo

| Ruolo | Funzione principale |
|---|---|
| [Capo Squadriglia](csq.md) | Compila i moduli del Diario di Bordo |
| [Capo Reparto](crp.md) | Integra il diario con la Relazione finale |
| [Pattuglia Guidoncini Verdi](pgv.md) | Valuta i diari assegnati |
| [Incaricato EG](incaricato.md) | Supervisiona le valutazioni e pubblica gli esiti |
| [Segreteria](segreteria.md) | Gestisce utenti, edizioni e import |
| [Amministratore](admin.md) | Configura la piattaforma, OAuth e autenticazione social |

---

## Struttura del Diario di Bordo

Il Diario è composto da sei moduli e segue un flusso a due fasi:

| Modulo | Titolo | Chi compila |
|---|---|---|
| 1 | Anagrafica | Capo Squadriglia / Capo Reparto |
| 2 | Presentazione squadriglia | Capo Squadriglia |
| 3 | 1ª Impresa | Capo Squadriglia |
| 4 | 2ª Impresa *(Rinnovo: facoltativo)* | Capo Squadriglia |
| 5 | Missione | Capo Squadriglia |
| 6 | Relazione finale | Capo Reparto *(mai visibile al Capo Squadriglia)* |

### Flusso di compilazione

1. Il **Capo Squadriglia** compila i moduli 1–5 e clicca **"Invia al Capo Reparto"** quando ha finito.
2. Il diario passa in stato **Relazione finale**: il **Capo Reparto** può ora compilare il modulo 6.
3. Il Capo Reparto clicca **"Invia diario allo staff"** per consegnare il diario completo.
4. Da questo momento il diario è in stato **Inviato** e non è più modificabile (salvo riapertura autorizzata).

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
