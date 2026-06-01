# Guida — Segreteria

La Segreteria gestisce gli utenti, le edizioni, gli import delle anagrafiche e le impostazioni
operative della piattaforma.

> La Segreteria deve configurare l'**autenticazione a due fattori (MFA)** al primo accesso.

---

## Home page

La home mostra l'edizione attiva con lo stato complessivo dei diari.

![Home Segreteria](screenshots/14_home_segreteria.png)

---

## Gestione utenti

Da **Gestione → Utenti** trovi l'elenco completo degli utenti della piattaforma.
Puoi filtrare per ruolo e cercare per nome o email.

![Lista utenti](screenshots/15_utenti_lista.png)

Per ogni utente puoi:

- Visualizzarne il profilo e il ruolo
- **Assegnare un ruolo** (Nomina): segreteria può creare utenti con ruolo CRP, PGV, CSQ,
  Incaricato EG e altri Segreteria
- Inviare un nuovo invito via email se l'utente non ha ancora attivato l'account

> La Segreteria **non può** creare o modificare account Admin.

---

## Impostazioni di piattaforma

Da **Gestione → Impostazioni** (visibile a Admin e Segreteria):

![Impostazioni](screenshots/16_impostazioni.png)

Le sezioni disponibili:

| Sezione | Cosa configuri |
|---|---|
| **Identità** | Titolo e sottotitolo mostrati nella navbar |
| **Footer** | Testo, etichetta link e URL del footer |
| **Posta elettronica** | Modalità di invio email, SMTP, indirizzo mittente |
| **Stato e diagnostica** | Modalità manutenzione, debug toolbar |
| **Import tracciati** | Avvio manuale degli import Co.Ca., Ragazzi, Evento |
| **Template email** | Personalizzazione in rich text delle email di sistema |

---

## Import anagrafiche

Da **Gestione → Import anagrafiche** trovi lo storico di tutti gli import eseguiti.

![Storico import](screenshots/17_import_storico.png)

I tre tipi di import (avviabili da Impostazioni o da riga di comando):

| Comando | Sorgente | Effetto |
|---|---|---|
| `import_coca` | CSV capi Co.Ca. | Crea/aggiorna Soci (categoria capo) |
| `import_ragazzi` | CSV ragazzi | Crea/aggiorna Soci (categoria ragazzo) |
| `import_squadriglie` | CSV Evento | Crea diari, lega CSQ per codice socio e CRP per email |

> I CSV reali non vanno mai caricati nel repository (contengono dati di minori).
> Usa sempre file di test dalla cartella `fixtures/`.

Ogni riga non riconciliata (CRP non trovato per email) viene segnalata nella schermata
di **riconciliazione manuale**, accessibile dallo storico import.

---

## Gestione edizioni

Da **Gestione → Elenco edizioni** puoi vedere e modificare le edizioni.

![Dettaglio edizione](screenshots/18_edizione_detail.png)

Per ogni edizione è possibile:

- Cambiare lo stato (Aperta → In valutazione → Chiusa)
- Impostare le date evento e le scadenze
- Collegare un account Google Drive per l'archiviazione dei file
- Aggiungere dilazioni per specifiche squadriglie

---

## Helpdesk

Dalla voce **Helpdesk** in navbar gestisci i ticket aperti da CSQ e CRP.
Puoi rispondere, prendere in carico e chiudere i ticket.

---

## Impersonazione utenti

La Segreteria può **impersonare** (accedere come) qualunque utente con rango inferiore
(non Admin) tramite il pulsante nella pagina di dettaglio utente.
Durante l'impersonazione appare un banner arancio in cima alla pagina.
Non è possibile impersonare un Admin.
