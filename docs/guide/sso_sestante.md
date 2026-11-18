# Integrazione SSO Sestante — Istruzioni per Claude Code

Leggi questo documento PRIMA di toccare codice relativo ad autenticazione, social login,
MFA o ruoli in Plancia. Il contratto completo, valido per tutte le piattaforme, è
`docs/INTEGRAZIONE-SSO.md` del repo `AGESCI-Campania/sestante`:
<https://raw.githubusercontent.com/AGESCI-Campania/sestante/main/docs/INTEGRAZIONE-SSO.md>.
In caso di dubbio prevale quello.

## Contesto

Sestante (`https://auth.agescicampania.net`) è l'Identity Provider SSO (Authentik) delle
piattaforme AGESCI Campania. Plancia è la piattaforma pilota, slug `plancia`.

Il login locale (email/password/MFA) resta attivo accanto all'SSO durante la transizione. Si
disattiva solo su conferma esplicita dell'utente, verificato che tutti gli utenti attivi
abbiano fatto almeno un login SSO riuscito. Non disattivarlo autonomamente.

## Configurazione

| Cosa | Valore |
|---|---|
| Provider allauth | `openid_connect`, provider id **`sestante`**, nome "SSO AGESCI Campania"; `SESTANTE_APP` in formato **`APPS`** (con `SERVERS` allauth scarta `SCOPE`), scope `openid profile email avatar` |
| Issuer / discovery | `https://auth.agescicampania.net/application/o/plancia/` (`SOCIAL_SESTANTE_SERVER_URL` per sovrascriverlo) |
| Credenziali | `SOCIAL_SESTANTE_CLIENT_ID`, `SOCIAL_SESTANTE_CLIENT_SECRET` in `.env` (mai nel repo) |
| Callback (blueprint) | `https://plancia.agescicampania.net/accounts/oidc/sestante/login/callback/` |
| Launch URL | `https://plancia.agescicampania.net/accounts/oidc/sestante/login/?next=/` |
| Blueprint | `blueprints/provider-plancia.yaml` nel repo `sestante` (lo gestisce l'utente) |

- La callback è quella di allauth 65.x (prefisso `oidc`, `SOCIALACCOUNT_OPENID_CONNECT_URL_PREFIX`
  di default). Se si aggiorna allauth verificarla con
  `reverse("openid_connect_callback", kwargs={"provider_id": "sestante"})` prima di toccare il
  blueprint.
- Senza `SOCIAL_SESTANTE_CLIENT_ID` il provider non viene configurato (`config/settings/base.py`)
  e il pulsante non compare: l'app parte comunque. Stessa regola per Google/Microsoft/Apple.
- Client id e secret si trovano in
  <https://auth.agescicampania.net/if/admin/#/core/providers> → `Plancia AGESCI Campania` → modifica.
- Il backend usa sempre l'URL pubblico di Sestante, mai l'alias Docker `sestante-server`
  (issuer diverso → token rifiutati). Plancia non va collegata alla rete di Sestante e
  Sestante non è una dipendenza d'avvio della unit systemd.

## Comportamento (`apps/accounts/adapters.py`)

**Primo login SSO** (`PlanciaSocialAccountAdapter.pre_social_login` / `save_user`):
- senza email nel claim → login rifiutato con messaggio, nessun account creato;
- più utenti Plancia con la stessa email (confronto case-insensitive) → rifiutato;
- un utente con quella email → collegato (non duplicato);
- nessuno → creato (auto-signup solo per `sestante`, `is_auto_signup_allowed`), ruolo CSQ
  salvo ruoli globali; nome = claim `name` intero, cognome vuoto (`populate_user`: authentik
  manda il nome intero anche in `given_name` e nessun `family_name`);
- le email arrivate da Sestante sono marcate verificate (altrimenti `ACCOUNT_EMAIL_VERIFICATION
  = "mandatory"` chiederebbe una conferma via email ai nuovi utenti).

**Ruoli globali** (`_sync_ruoli_globali`, a ogni login SSO):

| Gruppo nel claim `groups` | Ruolo Plancia |
|---|---|
| `admin-multipiattaforma` | `Ruolo.ADMIN` |
| `segreteria` | `Ruolo.SEGRETERIA` |

- Sono `Nomina` con **`da_sso=True`**: create quando il gruppo compare, revocate
  (`attiva=False`, record conservato per l'audit) quando sparisce. Gli altri gruppi
  Authentik sono ignorati.
- Le Nomine locali (`da_sso=False`), comprese quelle di Admin/Segreteria create in Plancia, e
  i ruoli PGV/CRP/CSQ/Incaricato EG non vengono mai toccati.
- Ruolo attivo: passa al nuovo ruolo globale se di rango maggiore; se era un ruolo globale
  revocato torna al ruolo attivo di rango più alto, altrimenti CSQ. Un superutente resta Admin.
- Claim letti da `extra_data["userinfo"]` (fallback `id_token`) con `_sestante_groups()`: in
  allauth ≥ 65.11 `extra_data` è `{"userinfo": {...}, "id_token": {...}}`.

**MFA**: la verifica Sestante. Plancia non la richiede a chi è entrato via SSO **in questa
sessione**: il criterio è `sessione_da_sestante(request)`, cioè
`{"method": "socialaccount", "provider": "sestante"}` in
`request.session["account_authentication_methods"]`. Lo usano `PlanciaMFAAdapter.is_mfa_enabled`
(durante il login) e la regola unica `adapters.mfa_da_configurare`, applicata da
`apps/api/auth.py` (403 `mfa_da_configurare` sull'API, tranne `/api/v1/me…`) e da
`MFAEnforcementMiddleware` (403 `403_mfa.html` sui percorsi Django). **Non** usare
l'esistenza di un `SocialAccount` collegato: un utente collegato che entra con la password
locale deve restare soggetto alla MFA di Plancia.

**Immagine del profilo** (scope `avatar`, `apps/accounts/avatar.py`, contratto § 5.1 e § 6 punto 7):
- `pre_social_login` legge `picture` da `extra_data["userinfo"]` e **toglie il data-URI** prima
  che allauth salvi l'account (gli URL restano); `allinea_avatar` per gli utenti esistenti (anche
  appena collegati per email), `save_user` per i nuovi.
- data-URI `image/jpeg|png|webp|gif`, ≤ 512 KB, verificato con Pillow (il formato deve
  corrispondere al tipo) → `User.avatar` (file in `media/avatar/`, nome casuale),
  `avatar_sha256` per riscriverlo solo se cambia, `avatar_da_sso=True`.
- URL (Gravatar) o `picture` assente → si toglie la foto solo se `avatar_da_sso`; gli URL non si
  scaricano. Senza `userinfo` (solo `id_token`) non si tocca niente.
- Un errore sulla foto va nel log (`apps.accounts.avatar`) e non blocca il login.
- Si serve solo dall'API autenticata (`/api/v1/me/avatar`, `/api/v1/utenti/{id}/avatar` per lo
  staff), mai da `/media/`. In Plancia non si carica: il profilo rimanda a Sestante.

**Logout**: chiude solo la sessione di Plancia (quella su Sestante resta). Un logout globale via
`end-session` si implementa solo se l'utente lo chiede.

Test: `apps/accounts/tests/test_sso_sestante.py`, `test_avatar.py`, `apps/api/tests/test_avatar.py`.

## Cosa NON fare

- Non disattivare il login locale.
- Non committare `SOCIAL_SESTANTE_CLIENT_ID` / `SOCIAL_SESTANTE_CLIENT_SECRET`.
- Non modificare il repo `sestante` né creare Provider/Application a mano: preparare il
  blueprint e consegnarlo all'utente (contratto § 4).
- Non cambiare la callback senza aggiornare il blueprint.
- Non far toccare al flusso SSO ruoli locali o Nomine con `da_sso=False`.
- Non impostare `SOCIALACCOUNT_AUTO_SIGNUP = True` globalmente.
- Non aggiungere redirect URI `localhost` al provider di produzione: per provare l'SSO in
  locale chiedere all'utente un provider di sviluppo separato.
