# Guida: Configurazione Autenticazione Social — Plancia

Stack: **django-allauth 65.18.0** · provider Google, Microsoft, Apple · modello utente custom `apps.accounts.User`

---

## 1. Architettura di riferimento

```
Browser → allauth socialaccount → provider OAuth → callback → allauth
    → SocialAccount (DB) → User (accounts.User) → LoginEvent (audit)
```

L'email ricavata dal provider deve corrispondere a un `User` già esistente (creato da Segreteria/Admin tramite `Invito`). Il social login **non crea nuovi utenti** da solo — vedi §5 per come bloccare la registrazione spontanea.

---

## 2. Compatibilità Dev / Produzione

| Provider | Funziona in dev? | Note |
|----------|-----------------|------|
| **Google** | ✓ **Sì**, con tunnel | Aggiungi `http://localhost:8000/...callback/` come URI autorizzato. Oppure usa ngrok per HTTPS. |
| **Microsoft** | ✓ **Sì**, con tunnel | Come Google; registra l'URI `localhost` nel portale Azure. |
| **Apple** | ✗ **No** (solo produzione) | Apple impone HTTPS e un dominio verificato. Non testabile in locale senza tunnel fisso e dominio reale. |

---

## 3. Variabili d'ambiente

Aggiungi in `.env.dev` (valori reali) e nel vault/secret di produzione.
I placeholder sono già in `.env.dev.example`.

```bash
# Google
SOCIAL_GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
SOCIAL_GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx

# Microsoft (Azure AD)
SOCIAL_MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
SOCIAL_MICROSOFT_CLIENT_SECRET=xxxxx~xxxxx

# Apple
SOCIAL_APPLE_CLIENT_ID=com.agescicampania.plancia   # Service ID, NON App ID
SOCIAL_APPLE_TEAM_ID=XXXXXXXXXX                      # 10 caratteri
SOCIAL_APPLE_KEY_ID=XXXXXXXXXX                       # ID chiave .p8
SOCIAL_APPLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----"
```

Lasciare una variabile vuota disattiva il relativo provider (nessun pulsante in pagina).

---

## 4. Come ottenere le credenziali

### 4.1 Google — Google Cloud Console

**Tempo stimato: ~10 minuti**

1. Vai su [console.cloud.google.com](https://console.cloud.google.com) e accedi con l'account Google del territorio (o uno tecnico).
2. **Crea un progetto** (menu a tendina in alto → "Nuovo progetto") → nome es. `Plancia AGESCI Campania`.
3. Nel menu laterale: **API e servizi** → **Schermata consenso OAuth**.
   - Tipo utente: **Esterno** (oppure **Interno** se il territorio ha Google Workspace — in quel caso solo gli utenti del dominio potranno accedere).
   - Compila: nome app (`Plancia`), email supporto, logo opzionale.
   - Aggiungi scope: cerca e aggiungi `email`, `profile`, `openid` (non servono scope sensibili).
   - Aggiungi gli indirizzi email degli sviluppatori come "tester" se l'app è in modalità Test.
4. **API e servizi** → **Credenziali** → **Crea credenziali** → **ID client OAuth 2.0**.
   - Tipo applicazione: **Applicazione web**.
   - Nome: `Plancia web`.
   - **URI di reindirizzamento autorizzati** — aggiungi tutti gli ambienti attivi:
     - Dev locale: `http://localhost:8000/accounts/google/login/callback/`
     - Dev con ngrok: `https://xxxx.ngrok.io/accounts/google/login/callback/`
     - Produzione: `https://plancia.agescicampania.org/accounts/google/login/callback/`
5. Clicca **Crea**. Si apre un popup con:
   - **ID client** → `SOCIAL_GOOGLE_CLIENT_ID`
   - **Secret client** → `SOCIAL_GOOGLE_CLIENT_SECRET`

> **Nota**: l'app rimane in modalità "Test" finché non la pubblichi. In modalità test solo i tester aggiunti al punto 3 possono autenticarsi. Per la produzione clicca **Pubblica app** nella schermata consenso (non richiede verifica per scope non sensibili come email/profile).

---

### 4.2 Microsoft — Azure / Microsoft Entra ID

**Tempo stimato: ~15 minuti**

1. Vai su [portal.azure.com](https://portal.azure.com) e accedi (basta un account Microsoft personale se non hai Azure aziendale).
2. Cerca **Microsoft Entra ID** nella barra di ricerca → **Registrazioni app** → **+ Nuova registrazione**.
   - Nome: `Plancia`.
   - Tipo account supportato:
     - **"Account in qualsiasi directory organizzativa e account Microsoft personali"** → lascia `"TENANT": "common"` nel settings (accetta tutti).
     - **"Solo questo tenant"** → usa il proprio Tenant ID → metti `"TENANT": "<tenant-id>"`.
   - URI di reindirizzamento: tipo **Web**, valore `https://plancia.agescicampania.org/accounts/microsoft/login/callback/`
     (aggiungi anche `http://localhost:8000/accounts/microsoft/login/callback/` per il dev).
3. Clicca **Registra**. Nella pagina dell'app appena creata:
   - **ID applicazione (client)** → `SOCIAL_MICROSOFT_CLIENT_ID`
4. Nel menu laterale: **Certificati e segreti** → **Segreti client** → **+ Nuovo segreto client**.
   - Descrizione: `plancia-prod`, scadenza: 24 mesi.
   - Clicca **Aggiungi**. Copia subito il **valore** (non l'ID!) → `SOCIAL_MICROSOFT_CLIENT_SECRET`
   - ⚠️ Il valore è visibile solo al momento della creazione. Se lo perdi devi rigenerarlo.
5. Nel menu laterale: **Autorizzazioni API** → verifica che `User.Read` (Microsoft Graph) sia presente. Se non c'è: **+ Aggiungi autorizzazione** → Microsoft Graph → Autorizzazioni delegate → `User.Read`.

---

### 4.3 Apple — Apple Developer Program

**Tempo stimato: ~30 minuti · Solo produzione (richiede HTTPS e dominio reale)**

Prerequisito: account [Apple Developer Program](https://developer.apple.com/programs/) attivo (99 $/anno). Per un'associazione no-profit come AGESCI potrebbe essere disponibile una tariffa agevolata o l'accesso gratuito.

1. Vai su [developer.apple.com](https://developer.apple.com) → **Account** → **Certificates, IDs & Profiles**.

2. **Crea o verifica l'App ID**
   - **Identifiers** → **+** → tipo **App IDs** → **App**.
   - Bundle ID: `org.agescicampania.plancia` (stile reverse-domain).
   - Scroll fino a **Capabilities** → abilita **Sign In with Apple**.
   - Salva. Annota l'**App ID Prefix** (= Team ID, 10 caratteri).

3. **Crea il Service ID** (è questo il `client_id` OAuth)
   - **Identifiers** → **+** → tipo **Services IDs**.
   - Description: `Plancia Sign In`, Identifier: `com.agescicampania.plancia` → `SOCIAL_APPLE_CLIENT_ID`.
   - Abilita **Sign In with Apple** → **Configure**:
     - Primary App ID: seleziona l'App ID del punto 2.
     - Domains: `plancia.agescicampania.org`
     - Return URLs: `https://plancia.agescicampania.org/accounts/apple/login/callback/`
   - Salva.

4. **Crea la chiave di firma**
   - **Keys** → **+** → nome `Plancia Sign In` → abilita **Sign In with Apple** → **Configure** → seleziona il Primary App ID.
   - Registra. Scarica il file `.p8` (**scaricabile una sola volta**).
   - Annota il **Key ID** (10 caratteri) → `SOCIAL_APPLE_KEY_ID`.

5. **Converti la chiave per l'env** (la chiave va su una riga con `\n` letterali):
   ```bash
   awk 'NF {printf "%s\\n", $0}' AuthKey_XXXXXXXXXX.p8
   ```
   Copia l'output completo (incluso `-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----`) come valore di `SOCIAL_APPLE_PRIVATE_KEY`.

6. **Variabili finali**:
   - `SOCIAL_APPLE_CLIENT_ID` = Identifier del Service ID (punto 3)
   - `SOCIAL_APPLE_TEAM_ID` = App ID Prefix / Team ID (punto 2, 10 caratteri in alto a destra del portale)
   - `SOCIAL_APPLE_KEY_ID` = Key ID (punto 4)
   - `SOCIAL_APPLE_PRIVATE_KEY` = contenuto `.p8` con `\n` letterali (punto 5)

---

## 5. Settings (`config/settings/base.py`)

Il blocco è già configurato nel progetto. Per riferimento:

```python
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {"client_id": _GOOGLE_CLIENT_ID, "secret": _GOOGLE_CLIENT_SECRET, "key": ""},
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "FETCH_USERINFO": True,
    },
    "microsoft": {
        "APP": {"client_id": _MS_CLIENT_ID, "secret": _MS_CLIENT_SECRET},
        "TENANT": "common",   # sostituire con Tenant ID per limitare a un'org
        "SCOPE": ["User.Read"],
    },
    "apple": {
        "APP": {
            "client_id": _APPLE_CLIENT_ID,
            "secret": _APPLE_PRIVATE_KEY,
            "key": _APPLE_KEY_ID,
            "certificate_key": _APPLE_PRIVATE_KEY,
        },
        "TEAM_ID": _APPLE_TEAM_ID,
    },
}

SOCIALACCOUNT_AUTO_SIGNUP = False                   # no nuovi utenti via social
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.PlanciaSocialAccountAdapter"
```

---

## 6. SITE_ID e record `django.contrib.sites`

allauth usa `SITE_ID = 1` (già impostato in `base.py`). Il record deve avere il dominio corretto.

```bash
# Dev
uv run python manage.py shell -c "
from django.contrib.sites.models import Site
s = Site.objects.get(pk=1); s.domain = 'localhost:8000'; s.name = 'Plancia (dev)'; s.save()
"

# Produzione
uv run python manage.py shell -c "
from django.contrib.sites.models import Site
s = Site.objects.get(pk=1); s.domain = 'plancia.agescicampania.org'; s.name = 'Plancia'; s.save()
"
```

---

## 7. Bloccare la registrazione spontanea via social

Il file `apps/accounts/adapters.py` è già presente nel progetto con `PlanciaSocialAccountAdapter`:

- `is_auto_signup_allowed` → sempre `False`: nessun `User` nuovo creato via social.
- `pre_social_login` → se l'email del provider combacia con un `User` esistente, lo collega automaticamente senza passare per il signup.

---

## 8. Template

I pulsanti social in `templates/account/login.html` sono già presenti:

```html
{% get_providers as socialaccount_providers %}
{% if socialaccount_providers %}
<hr class="my-3">
<div class="d-grid gap-2">
  {% for provider in socialaccount_providers %}
  <a href="{% provider_login_url provider.id %}" class="btn btn-outline-secondary">
    {% blocktrans with name=provider.name %}Accedi con {{ name }}{% endblocktrans %}
  </a>
  {% endfor %}
</div>
{% endif %}
```

Il blocco appare automaticamente solo se almeno un provider ha `client_id` valorizzato nell'env.

---

## 9. Migrations

```bash
uv run python manage.py showmigrations socialaccount sites
# Se necessario:
uv run python manage.py migrate
```

---

## 10. Audit (LoginEvent)

Il signal `on_login` in `apps/accounts/signals.py` registra il provider usato:
- `"google"` / `"microsoft"` / `"apple"` per login social
- stringa vuota per login email/password

Visibile in Admin → **Evento di login**.

---

## 11. Dev: testare Google o Microsoft senza dominio pubblico

```bash
# Avvia ngrok su una nuova finestra di terminale
ngrok http 8000
# Output: Forwarding https://xxxx.ngrok.io -> localhost:8000
```

1. Aggiungi `https://xxxx.ngrok.io/accounts/google/login/callback/` come URI autorizzato in Google Console (o Azure).
2. Aggiungi `xxxx.ngrok.io` in `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` nel `.env.dev`.
3. Usa il tunnel per accedere all'app; il callback OAuth funzionerà.

L'URL ngrok cambia a ogni avvio (piano gratuito). Per evitarlo usa il piano a pagamento o Cloudflare Tunnel che permette un dominio fisso gratuito.

---

## 12. Checklist di deploy

| Controllo | Dev | Prod |
|-----------|-----|------|
| Record Sites con dominio corretto | `localhost:8000` | dominio reale |
| Variabili env provider valorizzate | opzionale | obbligatorio se provider attivo |
| Redirect URI registrate nelle console | URI `localhost` o ngrok | URI HTTPS reale |
| `SOCIALACCOUNT_AUTO_SIGNUP = False` | ✓ | ✓ |
| `SOCIALACCOUNT_ADAPTER` impostato | ✓ | ✓ |
| `ACCOUNT_EMAIL_VERIFICATION` | `none` (dev.py) | `mandatory` (base.py) |
| Google: app pubblicata (non in modalità Test) | non necessario | ✓ |
| Apple: dominio verificato + HTTPS | ✗ non testabile | ✓ obbligatorio |
| Segreto Microsoft: non scaduto (24 mesi) | — | ✓ monitorare scadenza |
