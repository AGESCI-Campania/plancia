# Guida: Configurazione Google OAuth per Google Drive — Plancia

Stack: **google-auth-oauthlib** · scope `drive` · modello `DriveCredenziali` · view `DriveOAuthInitView` / `DriveOAuthCallbackView`

---

## 1. Funzionamento

```
Admin → /drive/oauth/init/?edizione=<pk>
     → Google OAuth consent screen
     → /drive/oauth/callback/ (exchange code → access+refresh token)
     → DriveCredenziali salvate in DB
     → redirect all'edizione
```

Il token viene usato da `apps.storage_drive.service` per:
- caricare i PDF dei diari su una cartella Drive dell'edizione,
- caricare l'Excel riepilogativo,
- creare sottocartelle per le foto degli allegati.

L'accesso a Drive è **per account Google** (il token appartiene all'account che ha completato il flusso OAuth). Conviene usare un account tecnico di territorio (es. `tecnico@agescicampania.org`) per centralizzare i permessi.

---

## 2. Stessa Google Cloud Console del social login

Se hai già un progetto GCP per il social login (vedi `docs/guide/social_auth.md`), puoi:

- **Riusare lo stesso progetto** — aggiungi lo scope Drive e un secondo URI di redirect alle credenziali esistenti.
- **Creare un progetto separato** — consigliato se vuoi separare i log di accesso e i limiti quota.

In entrambi i casi il procedimento è identico dal passo 3 in poi.

---

## 3. Abilita le API necessarie

1. Vai su [console.cloud.google.com](https://console.cloud.google.com) → seleziona il tuo progetto.
2. **API e servizi** → **Libreria**.
3. Cerca e abilita:
   - **Google Drive API** — obbligatoria per creare cartelle e caricare file.
   - **People API** o **Google+ API** — necessaria solo se non l'hai già abilitata per il social login (serve per recuperare l'email dell'account durante il flusso OAuth).

---

## 4. Schermata di consenso OAuth

Vai in **API e servizi** → **Schermata consenso OAuth**.

### Tipo utente

| Tipo | Quando usarlo |
|------|--------------|
| **Interno** | Solo se il territorio ha **Google Workspace** con dominio proprio. Solo gli utenti del dominio possono autorizzare. Non richiede verifica Google. |
| **Esterno** | Account Google personali o di altri domini. Richiede **verifica** se gli scope sono sensibili (vedi §5). |

Per le istanze AGESCI Campania con Google Workspace (`@agescicampania.org`) scegli **Interno** — è il percorso più semplice.

### Scope da aggiungere

Clicca **Modifica** → **Aggiungi o rimuovi scope** → cerca e aggiungi:

| Scope | Descrizione | Sensibile? |
|-------|-------------|------------|
| `openid` | Identità base | No |
| `.../auth/userinfo.email` | Email account | No |
| `.../auth/drive` | Accesso completo Drive | **Sì** |

> **Se il tipo è "Interno" (Google Workspace) non serve verifica** — puoi aggiungere scope sensibili liberamente.  
> Se è "Esterno" e vuoi evitare la verifica, usa `.../auth/drive.file` (solo file creati dall'app) oppure limita i tester nel passo successivo.

### Tester (solo tipo "Esterno" in modalità Test)

Aggiungi gli indirizzi email degli account Google che completeranno il flusso OAuth (es. l'account tecnico del territorio). Solo questi account possono autorizzare mentre l'app è in modalità Test.

---

## 5. Verifica dell'app Google (scope sensibili, tipo "Esterno")

Lo scope `https://www.googleapis.com/auth/drive` è classificato come **sensibile** da Google. Se il tipo utente è **Esterno** e vuoi che qualunque account (non solo i tester) completi il flusso OAuth, devi richiedere la verifica dell'app.

**Alternativa pratica (consigliata)**: usa il tipo **Interno** (Google Workspace) oppure tieni l'app in modalità **Test** e aggiungi come tester solo l'account tecnico che autorizza Drive. Per un uso interno a un'organizzazione questo è sufficiente.

---

## 6. Credenziali OAuth 2.0

### 6.1 Crea o aggiorna le credenziali

Vai in **API e servizi** → **Credenziali** → **Crea credenziali** → **ID client OAuth 2.0**  
(oppure modifica le credenziali esistenti se riusi il progetto del social login).

- Tipo applicazione: **Applicazione web**
- Nome: `Plancia Drive` (o `Plancia web` se unificato)

### 6.2 Aggiungi gli URI di reindirizzamento autorizzati

Aggiungi **tutti** gli ambienti che useranno il flusso Drive:

| Ambiente | URI |
|----------|-----|
| Dev locale | `http://localhost:8000/drive/oauth/callback/` |
| Dev con ngrok | `https://xxxx.ngrok.io/drive/oauth/callback/` |
| Produzione | `https://plancia.agescicampania.org/drive/oauth/callback/` |

> Nota: gli URI per il **social login** (allauth) e per **Drive** sono diversi.  
> Se usi le stesse credenziali devi avere entrambi i set di URI nella stessa voce.

### 6.3 Copia le credenziali

Dopo aver cliccato **Crea** (o **Salva**):
- **ID client** → `GOOGLE_OAUTH_CLIENT_ID`
- **Secret client** → `GOOGLE_OAUTH_CLIENT_SECRET`

---

## 7. Variabili d'ambiente

Aggiungi in `.env.dev` (valori reali, mai nel repository):

```bash
# Google OAuth — Drive integration
GOOGLE_OAUTH_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/drive/oauth/callback/
```

In `.env.prod`:

```bash
GOOGLE_OAUTH_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_OAUTH_REDIRECT_URI=https://plancia.agescicampania.org/drive/oauth/callback/
```

Il default `GOOGLE_OAUTH_REDIRECT_URI` in `config/settings/base.py` è già `http://localhost:8000/drive/oauth/callback/` — in dev puoi ometterla se usi la porta 8000.

---

## 8. Come autorizzare Drive da UI (flusso operativo)

1. Accedi con un account **Admin** o **Staff** (i soli che hanno accesso a `StaffPlanciaRequiredMixin`).
2. Vai in **Gestione → Elenco edizioni** → apri l'edizione.
3. Nella sezione Drive dell'edizione clicca **Autorizza Google Drive** (lancia `DriveOAuthInitView`).
4. Accedi con l'account Google che possiede (o ha accesso alla) cartella Drive del territorio.
5. Accetta le autorizzazioni richieste (Drive + email).
6. Vieni reindirizzato all'edizione. Da questo momento `DriveCredenziali` è salvato per l'edizione.

Il token include un **refresh token** (grazie a `access_type=offline` e `prompt=consent`): non scadrà a meno di non revocare l'accesso dal portale Google.

---

## 9. Dev locale: HTTP e OAUTHLIB_INSECURE_TRANSPORT

Google OAuth richiede HTTPS in produzione. Per dev su `localhost` (HTTP):

- La variabile `OAUTHLIB_INSECURE_TRANSPORT=1` viene impostata automaticamente in `DriveOAuthCallbackView` (`os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")`).  
  Non servono modifiche manuali per il solo flusso Drive.
- Se usi ngrok per HTTPS, puoi rimuovere quella riga o ignorarla (non crea problemi in produzione perché `setdefault` non sovrascrive se già impostata).

> **Non impostare `OAUTHLIB_INSECURE_TRANSPORT=1` in produzione** — Django non lo fa automaticamente, ma verifica che non sia presente nei tuoi script di avvio.

---

## 10. Revocare o rigenerare il token

Da Google:
- Vai su [myaccount.google.com/permissions](https://myaccount.google.com/permissions) con l'account usato per autorizzare.
- Cerca `Plancia` (o il nome app configurato) → **Rimuovi accesso**.

Da Plancia:
- Elimina il record `DriveCredenziali` dell'edizione da Admin → **Storage Drive → Drive credenziali**.
- Al prossimo export il task Celery fallirà chiedendo di rieseguire l'autorizzazione.

---

## 11. Differenza con il social login Google

| | Social login (`SOCIAL_GOOGLE_*`) | Drive (`GOOGLE_OAUTH_*`) |
|---|---|---|
| Libreria | `django-allauth` | `google-auth-oauthlib` |
| Scope | `openid`, `email`, `profile` | `drive`, `openid`, `email` |
| Scopo | Identificare l'utente che accede | Caricare file su Drive di un account tecnico |
| Token salvato | In `SocialToken` (allauth) | In `DriveCredenziali` (nostra app) |
| Account usato | Utente finale (ogni capo/admin) | Account tecnico del territorio |
| Variabili env | `SOCIAL_GOOGLE_CLIENT_ID/SECRET` | `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI` |

Possono condividere lo stesso **client OAuth** (stesse credenziali GCP) o avere client separati — entrambe le configurazioni funzionano. Se condivisi, assicurati che gli URI di redirect di entrambi i flussi siano aggiunti alle stesse credenziali.

---

## 12. Checklist di configurazione

| Controllo | Dev | Prod |
|-----------|-----|------|
| Google Drive API abilitata | ✓ | ✓ |
| Schermata consenso compilata con scope `drive` | ✓ | ✓ |
| Tipo utente "Interno" (Workspace) o tester aggiunti | ✓ | ✓ |
| URI `http://localhost:8000/drive/oauth/callback/` nelle credenziali | ✓ | — |
| URI produzione nelle credenziali | — | ✓ |
| `GOOGLE_OAUTH_CLIENT_ID` e `SECRET` nel `.env` | ✓ | ✓ |
| `GOOGLE_OAUTH_REDIRECT_URI` produzione nel `.env.prod` | — | ✓ |
| Token autorizzato via UI (edizione) | per ogni edizione | per ogni edizione |
| `OAUTHLIB_INSECURE_TRANSPORT` assente in prod | — | ✓ verifica |
