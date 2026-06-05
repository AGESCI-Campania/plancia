# Configurazione provider email

Plancia supporta **due backend email indipendenti** configurabili in **Impostazioni → Posta elettronica**:

| Backend | Uso consigliato | Tracking bounce |
|---|---|---|
| **SMTP** (normale o Gmail OAuth2) | Email di sistema, inviti singoli | No |
| **Provider transazionale** (Brevo, Mailgun, ecc.) | Inviti bulk CRP/CSQ | Sì |

I due backend possono essere attivi contemporaneamente e vengono selezionati automaticamente
in base al **tipo di invio** (vedi sezione Routing).

---

## Routing per tipo di invio

In **Impostazioni → Posta elettronica** sono presenti due campi di routing:

| Campo | Default | Quando viene usato |
|---|---|---|
| **Backend email standard** | SMTP | Reset password, MFA, inviti singoli, notifiche |
| **Backend invii massivi** | Provider transazionale | Inviti bulk Capi Reparto e Capi Squadriglia |

Nella pagina **Gestione Inviti**, prima di avviare un invio bulk, è possibile **sovrascrivere** il
backend predefinito selezionando esplicitamente SMTP o il provider transazionale.

> La **Modalità email** (Simulato / Mailpit / Invio reale) sovrascrive entrambi i backend:
> - *Simulato* → tutti i messaggi vanno su file, nessuno viene inviato
> - *Mailpit* → tutti i messaggi vengono intercettati da Mailpit
> - *Invio reale* → usa i backend configurati con il routing

---

## Backend SMTP

### SMTP classico (username + password)

Seleziona **SMTP** come backend e compila i campi:

| Campo | Descrizione |
|---|---|
| SMTP host | Indirizzo del server (es. `smtp.gmail.com`) |
| SMTP porta | Di solito `587` (STARTTLS) o `465` (SSL) |
| SMTP utente | Username dell'account SMTP |
| SMTP password | Password o App Password |
| Usa TLS | Abilitato per STARTTLS |

### Gmail OAuth2 SMTP (consigliato per Gmail)

Google richiede OAuth2 per l'accesso SMTP a Gmail senza App Password. Plancia supporta
l'autenticazione **XOAUTH2** su `smtp.gmail.com:587`.

#### Passo 1 — Abilita Gmail API in Google Cloud Console

1. Vai su [console.cloud.google.com](https://console.cloud.google.com) → seleziona
   il progetto già usato per il Drive OAuth.
2. **API e servizi → Libreria** → cerca **Gmail API** → **Abilita**.

#### Passo 2 — Aggiungi il redirect URI alle credenziali OAuth

Nelle stesse credenziali OAuth usate per il Drive (`GOOGLE_OAUTH_CLIENT_ID`):

1. **API e servizi → Credenziali** → clicca sull'ID client OAuth esistente.
2. Aggiungi in **URI di reindirizzamento autorizzati**:
   - Dev: `http://localhost:8000/impostazioni/gmail-smtp/oauth/callback/`
   - Produzione: `https://plancia.agescicampania.org/impostazioni/gmail-smtp/oauth/callback/`
3. Salva.

#### Passo 3 — Aggiungi la variabile d'ambiente

In `.env.prod` aggiungi:
```bash
GOOGLE_GMAIL_SMTP_REDIRECT_URI=https://plancia.agescicampania.org/impostazioni/gmail-smtp/oauth/callback/
```

In `.env.dev`:
```bash
GOOGLE_GMAIL_SMTP_REDIRECT_URI=http://localhost:8000/impostazioni/gmail-smtp/oauth/callback/
```

#### Passo 4 — Collega l'account Gmail

1. Vai su **Impostazioni → Posta elettronica → Backend SMTP**.
2. Clicca **Collega Gmail**.
3. Accedi con l'account Gmail da cui vuoi inviare le email (es. `noreply@agescicampania.org`).
4. Autorizza l'accesso — Plancia salva il refresh token e non richiede più la password.
5. Il badge **Attivo: nome@gmail.com** conferma il collegamento.

> **Rinnovo automatico del token**: il token di accesso dura circa 1 ora. Plancia lo rinnova
> automaticamente prima dell'invio usando il refresh token. Non è necessaria nessuna azione manuale.

> **Revoca**: se revochi l'accesso da [myaccount.google.com/permissions](https://myaccount.google.com/permissions),
> clicca **Scollega** in Impostazioni e ripeti il collegamento.

#### Nota sulle verifiche Google

Se il progetto Google Cloud non è in produzione verificata, potresti vedere un avviso
"App non verificata" durante il collegamento. Puoi procedere cliccando **Avanzate → Vai a Plancia**.
Per rimuovere l'avviso, completa il processo di verifica dell'app in Google Cloud Console.

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

Il campo **Modalità email** in Impostazioni è indipendente dal provider e sovrascrive
il routing per tipo:

| Modalità | Comportamento |
|---|---|
| Simulato | Non invia: scrive i messaggi in `logs/email/` (file `.eml`) |
| Invio reale | Usa i backend configurati con il routing per tipo |
| Simulato + invio reale | Scrive su file E invia via backend configurato |
| Mailpit (debug) | Intercetta tutto su Mailpit locale (`/mailadmin/`, solo staff) |

---

## Mailpit in produzione (debug)

Mailpit è incluso nel `docker-compose.prod.yml` come servizio interno (nessuna porta esposta).

Per abilitarlo:

1. In **Impostazioni → Posta elettronica**: seleziona modalità **Mailpit (debug)**.
2. Accedi alla web UI di Mailpit su `https://tuo-dominio.org/mailadmin/` (richiede login admin).
3. Quando hai finito il debug, torna alla modalità **Invio reale**.

> La web UI `/mailadmin/` è protetta dalla sessione Django: deve essere loggato un utente con
> ruolo Admin, Segreteria o Incaricato EG. Non è accessibile pubblicamente.
