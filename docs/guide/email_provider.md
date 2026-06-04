# Configurazione provider email

Plancia supporta due modalità di invio email, configurabili da **Impostazioni → Posta elettronica**:

| Modalità | Provider | Tracking bounce/errori |
|---|---|---|
| **SMTP tradizionale** | Qualsiasi server SMTP | No |
| **Provider transazionale** | Brevo, Mailgun, MailerSend, Postmark, SendGrid, SparkPost, Amazon SES | Sì |

La scelta del provider avviene in **Impostazioni → Posta elettronica → Provider email**.

---

## SMTP tradizionale

Seleziona **SMTP tradizionale** e compila i campi:

| Campo | Descrizione |
|---|---|
| SMTP host | Indirizzo del server (es. `smtp.gmail.com`) |
| SMTP porta | Di solito `587` (STARTTLS) o `465` (SSL) |
| SMTP utente | Username dell'account SMTP |
| SMTP password | Password o App Password |
| Usa TLS | Abilitato per STARTTLS, disabilitato per connessione plain |

Nessuna configurazione aggiuntiva sul server richiesta.

---

## Provider transazionali (django-anymail)

Con i provider transazionali Plancia registra lo stato di consegna di ogni email di invito
(inviato → consegnato / bounce / spam / errore) visibile nella pagina **Gestione Inviti**.

### Passaggi generali

1. Crea un account sul provider scelto e ottieni l'**API key**.
2. In **Impostazioni → Posta elettronica**: seleziona il provider e incolla l'API key.
3. **Webhook**: configura l'URL di tracking nel pannello del provider:
   ```
   https://plancia.agescicampania.org/anymail/webhook/
   ```
4. Copia il **webhook secret** (fornito dal provider) nel campo apposito in Impostazioni.
5. Salva e verifica con un invito di prova.

---

### Brevo (ex Sendinblue)

1. **API key**: [Pannello Brevo](https://app.brevo.com) → Impostazioni → Chiavi API → Crea nuova chiave API (accesso "transazionale").
2. **Webhook**: Impostazioni → Messaggistica → Webhook → Aggiungi nuovo webhook.
   - URL: `https://tuo-dominio.org/anymail/webhook/`
   - Seleziona eventi: *Rimbalzo* (Bounce), *Hard bounce*, *Spam*, *Consegnato*.
   - Il campo **Secret** non è richiesto da Brevo (lascia vuoto in Impostazioni).
3. **Dominio mittente**: verifica il dominio del mittente in Impostazioni Brevo → Mittenti.

---

### Mailgun

1. **API key**: [Pannello Mailgun](https://app.mailgun.com) → Impostazioni → Chiavi API → API privata.
2. **Webhook signing key**: Mailgun → Impostazioni → Webhook → Signing key (diversa dall'API key).
   Incollala nel campo **Webhook secret** in Impostazioni.
3. **Webhook**: Sending → Webhooks → Aggiungi webhook.
   - URL: `https://tuo-dominio.org/anymail/webhook/`
   - Seleziona eventi: Delivered, Failed, Complained (spam), Bounced.
4. **Dominio mittente**: Mailgun richiede un dominio verificato. Aggiungi i record DNS richiesti.

---

### MailerSend

1. **API token**: [Pannello MailerSend](https://app.mailersend.com) → Impostazioni → Chiavi API → Crea token (permessi: email - invio).
2. **Webhook**: Impostazioni del dominio → Webhooks → Aggiungi webhook.
   - URL: `https://tuo-dominio.org/anymail/webhook/`
   - MailerSend genera un **Signing secret** — copialo nel campo Webhook secret.
   - Seleziona eventi: Delivered, Bounced, Spam complaint, Failed.

---

### Postmark

1. **Server token**: [Pannello Postmark](https://account.postmarkapp.com) → Server → Tokens API.
   Usa il **Server Token** (non l'Account Token).
2. **Webhook**: Server → Webhooks → Aggiungi webhook.
   - URL: `https://tuo-dominio.org/anymail/webhook/`
   - Seleziona: Delivery, Bounce, Spam Complaint.
   - In **Webhook password**: imposta un valore a scelta — copialo nel campo Webhook secret.

---

### SendGrid

1. **API key**: [Pannello SendGrid](https://app.sendgrid.com) → Impostazioni → Chiavi API → Crea chiave (permesso: Mail Send).
2. **Webhook**: Impostazioni → Event Notifications.
   - URL: `https://tuo-dominio.org/anymail/webhook/`
   - Attiva: Delivered, Bounce, Spam Report, Group Unsubscribe.
   - SendGrid fornisce una **Event Webhook Verification Key** — copiala nel campo Webhook secret.

> **Nota**: SendGrid usa una firma ECDSA per i webhook; incolla la chiave pubblica (formato `MFkw...`) nel campo Webhook secret.

---

### SparkPost

1. **API key**: [Pannello SparkPost](https://app.sparkpost.com) → Impostazioni → Chiavi API → Crea chiave (Transmissions - lettura/scrittura).
2. **Webhook**: Impostazioni → Webhooks → Crea webhook.
   - Target URL: `https://tuo-dominio.org/anymail/webhook/`
   - Seleziona: Delivery, Bounce, Spam Complaint.
   - Il Webhook secret non è supportato da SparkPost — lascia vuoto.

---

### Amazon SES

Amazon SES usa credenziali IAM (non API key). **Non compilare il campo API key**.

1. Configura le credenziali AWS sul server di produzione tramite variabili d'ambiente IAM:
   ```bash
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   AWS_DEFAULT_REGION=eu-west-1
   ```
2. Assicurati che l'identità IAM abbia il permesso `ses:SendEmail`.
3. **Webhook SNS**: crea un topic SNS in AWS per gli eventi (Bounce, Complaint, Delivery) e configura
   SNS per inviare notifiche HTTP all'URL: `https://tuo-dominio.org/anymail/webhook/`.
4. Lascia vuoto il campo Webhook secret (la verifica usa la firma SNS).

---

## Tracking nella piattaforma

Una volta configurato un provider transazionale, la colonna **stato consegna** nella pagina
**Gestione Inviti** mostra per ogni invito:

| Stato | Significato |
|---|---|
| *(vuoto)* | Email inviata ma nessuna conferma dal provider (normale con SMTP) |
| Inviato al provider | Email accettata dal provider per la consegna |
| Consegnato | Email consegnata al server di posta del destinatario |
| Bounce | Email respinta (indirizzo inesistente, casella piena, ecc.) |
| Spam | Il destinatario ha segnalato l'email come spam |
| Errore | Il provider ha segnalato un errore di invio |

In caso di **Bounce** o **Errore**, il dettaglio è visibile passando il mouse sul badge.

---

## Modalità di invio (email_mode)

Il campo **Modalità email** in Impostazioni è indipendente dal provider:

| Modalità | Comportamento |
|---|---|
| Simulato | Non invia: scrive i messaggi in `logs/email/` (file `.eml`) |
| Invio reale | Invia via provider configurato |
| Simulato + invio reale | Fa entrambe le cose (utile per il debug) |
| Mailpit (debug) | Invia a Mailpit locale, visibile su `/mailadmin/` (solo staff) |

La modalità **Mailpit** è pensata per il debug in produzione: tutte le email vengono intercettate
da Mailpit senza raggiungere i destinatari reali. Vedi la sezione successiva.

---

## Mailpit in produzione (debug)

Mailpit è incluso nel `docker-compose.prod.yml` come servizio interno (nessuna porta esposta).

Per abilitarlo:

1. In **Impostazioni → Posta elettronica**: seleziona modalità **Mailpit (debug)**.
2. Accedi alla web UI di Mailpit su `https://tuo-dominio.org/mailadmin/` (richiede login admin).
3. Quando hai finito il debug, torna alla modalità **Invio reale**.

> La web UI `/mailadmin/` è protetta dalla sessione Django: deve essere loggato un utente con
> accesso staff (`is_staff=True`). Non è accessibile pubblicamente.
