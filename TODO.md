# TODO — Plancia

## Errori preesistenti / Bug noti

_Nessuno al momento._

---

## Piani futuri

### App mobile "Diari di Bordo" (Flutter)

Repository separato: `diario-di-bordo-app` (accanto a `plancia/`).  
Versioning indipendente dalla PWA, parte da `1.0.0`. Targets Plancia API v1.  
Piattaforme: iOS + Android.

#### Step 1 — Scaffolding progetto ✅

- [x] `flutter create --org org.antaresnet --platforms ios,android appgv`
- [x] Bundle ID: `org.antaresnet.appgv` (iOS e Android)
- [x] Cartella rinominata in `diario-di-bordo-app`, nome display "Diari di Bordo"
- [x] Git inizializzato, primo commit
- [x] Struttura cartelle `lib/core/`, `lib/features/`, `lib/shared/`, `assets/`
- [x] Icone PWA copiate in `assets/icons/` (192, 512, 1024px)

#### Step 2 — Dipendenze (`pubspec.yaml`)

- [ ] `dio` — client HTTP con interceptors
- [ ] `hooks_riverpod` + `riverpod_annotation` — state management
- [ ] `go_router` — navigazione con route guards
- [ ] `flutter_secure_storage` — Keychain/Keystore per X-Session-Token e PIN
- [ ] `local_auth` — FaceID, TouchID, Fingerprint
- [ ] `reactive_forms` — form moduli 1–5 con validazione
- [ ] `flutter_svg` — icone SVG AGESCI
- [ ] `flutter_native_splash` — splash screen
- [ ] `intl` — localizzazione italiana

#### Step 3 — Design system e tema

- [ ] `lib/core/theme/plancia_colors.dart`: palette AGESCI (verde #5AA02C, viola #7A1E99, giallo #FFCC1E)
- [ ] `lib/core/theme/plancia_theme.dart`: `ThemeData` con `ColorScheme.fromSeed(verdePrimario)` Material 3
- [ ] Chip colori stati FSM (mappati 1:1 con la web app)
- [ ] Copiare `icon-1024x1024.png` e `icon-512x512.png` da `plancia/static/images/icons/`
- [ ] Configurare `flutter_native_splash` (sfondo bianco + logo)

#### Step 4 — Layer API (`lib/core/api/`)

- [ ] `api_client.dart`: Dio con base URL configurabile (dev/prod), interceptor X-Session-Token
- [ ] Interceptor per errori: 401 inaspettato → logout forzato; 503 → pagina manutenzione
- [ ] `auth_api.dart`: login, MFA (allauth headless `/app/v1/`)
- [ ] `diari_api.dart`: CRUD moduli, azioni FSM, valutazione
- [ ] `editions_api.dart`, `org_api.dart`, `me_api.dart`

#### Step 5 — Modelli (`lib/core/models/`)

- [ ] `diario.dart` (con stati FSM come enum)
- [ ] `moduli.dart` (Anagrafica, Presentazione, Impresa, Missione, RelazioneFinale, Valutazione)
- [ ] `edizione.dart`, `org.dart`, `utente.dart`
- [ ] Serializzazione JSON (`fromJson`/`toJson`) — no code generation per ora, manuale

#### Step 6 — Autenticazione e gate biometrico

- [ ] `lib/core/auth/auth_service.dart`: login, logout, salvataggio/lettura token da secure_storage
- [ ] `lib/features/auth/login_page.dart`: form email/password
- [ ] `lib/features/auth/mfa_page.dart`: inserimento codice TOTP
- [ ] `lib/features/auth/biometric_gate_page.dart`: FaceID/TouchID con fallback PIN
- [ ] `lib/features/auth/pin_setup_page.dart`: setup PIN 6 cifre (primo accesso)
- [ ] `lib/features/auth/pin_page.dart`: inserimento PIN
- [ ] Timeout: dopo 5 minuti in background → ripresenta il gate
- [ ] PIN hashato SHA-256 + salt prima di salvarlo

#### Step 7 — Navigazione (`go_router`)

- [ ] Route guard: se nessun token → redirect a `/login`
- [ ] Route guard: se token presente ma gate non superato → redirect a `/gate`
- [ ] Rotte principali: `/login`, `/gate`, `/pin`, `/home`, `/diari`, `/diari/:id`, `/diari/:id/modulo/:n`, `/edizioni`, `/profilo`

#### Step 8 — Schermate core

- [ ] `DiariListPage`: lista diari filtrata per ruolo, filtri per edizione/stato
- [ ] `DiarioDetailPage`: dettaglio read-only con tutti i moduli visibili per ruolo
- [ ] `Modulo1EditPage` (Anagrafica): form con optimistic locking, dialog su 409
- [ ] `Modulo2EditPage` (Presentazione)
- [ ] `ImpreseEditPage` (Imprese 1 e 2)
- [ ] `MissioneEditPage`
- [ ] `RelazioneFinaleEditPage` (solo CRP)
- [ ] Dialog conferma azioni FSM: "Invia", "Riapri"

#### Step 9 — Valutazione

- [ ] `ValutazionePage`: visibilità condizionale per ruolo (CSQ vede solo se pubblicata)
- [ ] Form valutazione diretta (Incaricato EG)
- [ ] Form proposta PGV
- [ ] Conferma/rigetto proposta (Incaricato EG)
- [ ] Bottone pubblica esito

#### Step 10 — Schermate secondarie

- [ ] `EdizioniListPage` + `EdizioneDetailPage`
- [ ] `AlberoOrgPage` (zone → gruppi → reparti → squadriglie, TreeView)
- [ ] `ProfiloPage`: nome, ruolo, logout

#### Step 11 — Gestione errori e UX

- [ ] Pagina "Servizio in manutenzione" (503)
- [ ] Banner offline con timestamp ultimo aggiornamento (cache in memoria)
- [ ] Loading skeleton sui list/detail
- [ ] Empty state con illustrazione

#### Step 12 — Localizzazione

- [ ] `AppLocalizations` con file `.arb` in italiano
- [ ] Stringhe: stati FSM, ruoli, messaggi di errore API

#### Step 13 — Configurazione build

- [ ] Flavor dev/prod (base URL API diverso)
- [ ] `--dart-define=API_BASE_URL=...` per CI
- [ ] Bundle ID, nome app, icone nei manifest Android/iOS
- [ ] Configurare firme (keystore Android, provisioning iOS) — da fare al momento del primo rilascio

#### Step 14 — Test e verifica

- [ ] Test widget: gate biometrico, login flow, conflict dialog 409
- [ ] Test integration: login → visualizza diario → modifica modulo 1 → invia
- [ ] Verifica manuale su simulatore iOS e dispositivo Android fisico
- [ ] Verifica invisibilità modulo 6 e valutazione non pubblicata al CSQ

#### Step 15 — Distribuzione (da fare dopo i test)

- [ ] App Store Connect: nuovo bundle, screenshot, descrizione
- [ ] Google Play Console: nuovo package, screenshot, descrizione
- [ ] Configurare CORS in produzione (`CORS_ALLOWED_ORIGINS` con schema app mobile se necessario)
- [ ] Aggiornare `docs/api/overview.md` con note mobile
