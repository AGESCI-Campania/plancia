# Integrazione SSO Sestante — Istruzioni per Claude Code

Leggi questo documento PRIMA di toccare codice relativo ad autenticazione, social login,
MFA o ruoli in Plancia.

## Contesto

Sestante (`auth.agescicampania.org`) è l'Identity Provider SSO basato su Authentik per
tutte le piattaforme AGESCI Campania. Plancia è la prima piattaforma client collegata (Fase 1).

Il login locale (email/password/MFA) rimane attivo in parallelo per 60 giorni dal rollout.
Solo dopo la verifica che tutti gli utenti attivi abbiano fatto almeno un login SSO riuscito
si valuterà la disattivazione del login locale. Non disattivarlo autonomamente.

## Stato dell'implementazione

Le modifiche Fase 1 sono **già presenti nel codice** (commit Fase 1):

| File | Cosa è stato fatto |
|---|---|
| `config/settings/base.py` | Aggiunto `openid_connect` a INSTALLED_APPS e SOCIALACCOUNT_PROVIDERS |
| `apps/accounts/adapters.py` | Estesa `PlanciaSocialAccountAdapter` con auto-signup e sync ruoli |
| `apps/accounts/middleware.py` | Bypass MFA enforcement per sessioni SSO Sestante |

## Architettura SSO

### Provider OIDC

Il provider è configurato in `SOCIALACCOUNT_PROVIDERS["openid_connect"]` con `id="sestante"`.
La discovery URL è `https://auth.agescicampania.org/application/o/plancia/`.

Le credenziali (`client_id`, `client_secret`) stanno in `.env.prod` come:
```
SOCIAL_SESTANTE_CLIENT_ID=...
SOCIAL_SESTANTE_CLIENT_SECRET=...
```
Non committarle mai. Vengono copiate dall'UI Authentik dopo l'applicazione del blueprint
`blueprints/provider-plancia.yaml` nel repo Sestante.

### URL di callback

```
https://plancia.agescicampania.org/accounts/openid_connect/sestante/login/callback/
```
(configurato nel blueprint Authentik, non modificarlo senza aggiornare anche il blueprint)

### Auto-provisioning

Gli utenti Authentik che non hanno ancora un account Plancia vengono creati automaticamente
al primo login SSO, **senza ruolo locale** (default `Ruolo.CSQ`), salvo abbiano già un ruolo
globale nel claim `groups` (→ ricevono `ADMIN` o `SEGRETERIA`).

### Sincronizzazione ruoli globali

Ad ogni login SSO, `PlanciaSocialAccountAdapter` legge il claim `groups` dall'`extra_data`
del social account e aggiorna `user.ruolo` secondo questa logica:

| Claim Sestante | user.ruolo Plancia |
|---|---|
| `admin-multipiattaforma` | `Ruolo.ADMIN` |
| `segreteria` | `Ruolo.SEGRETERIA` |
| nessuno dei due (se ruolo era globale) | reset a `Ruolo.CSQ` |
| nessuno dei due (se ruolo era locale) | invariato |

I ruoli locali (PGV, CRP, CSQ, INCARICATO_EG) **non vengono mai toccati** dal flusso SSO.
La fonte del claim è `extra_data["userinfo"]["groups"]`. In allauth ≥65.11, `extra_data` ha
struttura `{"userinfo": {...}, "id_token": {...}}`; non usare `extra_data.get("groups")` direttamente.
Usare l'helper `_sestante_groups(extra_data)` definito in `adapters.py`.

### MFA

Gli utenti che accedono tramite Sestante bypassano il `MFAEnforcementMiddleware` di Plancia:
la MFA è già stata completata su Sestante prima del redirect. Il bypass è attivo finché esiste
un record `SocialAccount` con `provider="sestante"` per l'utente.

## Cosa NON fare

- Non disattivare il login locale (è Fase 1, transizione in corso)
- Non committare `SOCIAL_SESTANTE_CLIENT_ID` o `SOCIAL_SESTANTE_CLIENT_SECRET`
- Non modificare la `redirect_uri` senza aggiornare il blueprint Sestante
- Non forzare MFA su Plancia per utenti con `SocialAccount.provider="sestante"`
- Non far toccare al flusso SSO ruoli locali (PGV, CRP, CSQ, INCARICATO_EG)
- Non impostare `SOCIALACCOUNT_AUTO_SIGNUP = True` globalmente (l'override per Sestante
  è già nel metodo `is_auto_signup_allowed` dell'adapter)

## Riferimenti

- Blueprint Sestante: `blueprints/provider-plancia.yaml` nel repo `/opt/sestante`
- Adapter: `apps/accounts/adapters.py` — `PlanciaSocialAccountAdapter`
- Middleware MFA: `apps/accounts/middleware.py` — `MFAEnforcementMiddleware._deve_forzare_setup`
- Settings OIDC: `config/settings/base.py` — `SOCIALACCOUNT_PROVIDERS["openid_connect"]`
- Guida social login generale: `docs/guide/social_auth.md`
