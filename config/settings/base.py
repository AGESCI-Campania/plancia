# config/settings/base.py
"""Impostazioni condivise. Override in dev.py / prod.py."""
import subprocess
import tomllib
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Versione e commit (GET /api/v1/sito, pagina Aggiornamenti) -------------
def _read_app_version() -> str:
    try:
        with open(BASE_DIR / "pyproject.toml", "rb") as _f:
            return tomllib.load(_f).get("project", {}).get("version", "?")
    except Exception:
        return "?"


def _read_app_commit() -> str:
    # Legge il commit direttamente dai file .git/ (non richiede il binario git,
    # che non è presente nell'immagine Docker python:3.14-slim).
    try:
        git_dir = BASE_DIR / ".git"
        head = (git_dir / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref_path = git_dir / head[5:]          # es. refs/heads/main
            if ref_path.exists():
                return ref_path.read_text().strip()[:7]
            # Prova packed-refs
            packed = git_dir / "packed-refs"
            if packed.exists():
                ref_name = head[5:]
                for line in packed.read_text().splitlines():
                    if not line.startswith("#") and line.endswith(ref_name):
                        return line.split()[0][:7]
        return head[:7]             # detached HEAD
    except Exception:
        pass
    # Fallback: prova con il binario git se disponibile
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=BASE_DIR, timeout=3,
        )
        return r.stdout.strip() or "?"
    except Exception:
        return "?"


APP_VERSION = _read_app_version()
APP_COMMIT = _read_app_commit()

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
# Carica un eventuale file .env (dev: .env.dev). In produzione le variabili arrivano
# dal .env del compose (env_file), il file non è nell'immagine.
_env_file = env.str("DJANGO_ENV_FILE", default=str(BASE_DIR / ".env.dev"))
if Path(_env_file).exists():
    environ.Env.read_env(_env_file)

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
SKIP_MFA_ENFORCEMENT = env.bool("SKIP_MFA_ENFORCEMENT", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Applicazioni -----------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.mfa",
    "allauth.mfa.webauthn",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.microsoft",
    "allauth.socialaccount.providers.apple",
    "allauth.socialaccount.providers.openid_connect",
    "allauth.usersessions",
    "guardian",
    "axes",
    "hijack",  # solo helper/segnali/middleware per l'impersonazione via API (nessun URL)
    "anymail",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.org",
    "apps.editions",
    "apps.diaries",
    "apps.evaluations",
    "apps.notifications",
    "apps.storage_drive",
    "apps.exports",
    "apps.helpdesk",
    "apps.stats",
    "apps.siteconfig",
    "apps.imports",
    "apps.aggiornamenti",
    "apps.api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Invia SECURE_CSP (definita in prod.py; vuota in dev = nessuna intestazione)
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.siteconfig.middleware.ApiRateLimitMiddleware",
    "apps.siteconfig.middleware.AppVersionMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "allauth.usersessions.middleware.UserSessionsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.siteconfig.middleware.AxesSettingsSyncMiddleware",
    "axes.middleware.AxesMiddleware",
    "hijack.middleware.HijackUserMiddleware",
    "apps.accounts.middleware.MFAEnforcementMiddleware",
    "apps.siteconfig.middleware.MaintenanceModeMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database ---------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://plancia:plancia@localhost:5432/plancia",
    ),
}

# --- Auth -------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    # axes in testa per bloccare i tentativi bruteforce prima dell'auth
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "guardian.backends.ObjectPermissionBackend",
]

# --- django-axes (brute-force) -----------------------------------------------
# Limite tentativi e cooloff letti da DB (Impostazioni) tramite callable.
AXES_FAILURE_LIMIT = "apps.siteconfig.axes_helpers.axes_failure_limit"
AXES_COOLOFF_TIME = "apps.siteconfig.axes_helpers.axes_cooloff_time"
AXES_LOCKOUT_PARAMETERS = ["ip_address"]  # blocca per IP

# allauth: solo headless (la SPA). LOGIN_URL è la pagina di accesso della SPA, usata da admin
# e proxy per chi non è autenticato.
LOGIN_URL = "/accesso"
LOGIN_REDIRECT_URL = "/"
# Login con email o codice socio: gli utenti nati da un Socio hanno come username il codice
# (notifications.service.crea_o_ottieni_utente_per_socio), i Capi Squadriglia spesso non hanno
# un'email vera. La SPA invia `username` se l'identificativo non contiene "@".
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
_GOOGLE_CLIENT_ID     = env.str("SOCIAL_GOOGLE_CLIENT_ID", default="")
_GOOGLE_CLIENT_SECRET = env.str("SOCIAL_GOOGLE_CLIENT_SECRET", default="")
_MS_CLIENT_ID         = env.str("SOCIAL_MICROSOFT_CLIENT_ID", default="")
_MS_CLIENT_SECRET     = env.str("SOCIAL_MICROSOFT_CLIENT_SECRET", default="")
_APPLE_CLIENT_ID      = env.str("SOCIAL_APPLE_CLIENT_ID", default="")
_APPLE_TEAM_ID        = env.str("SOCIAL_APPLE_TEAM_ID", default="")
_APPLE_KEY_ID         = env.str("SOCIAL_APPLE_KEY_ID", default="")
_APPLE_PRIVATE_KEY    = env.str("SOCIAL_APPLE_PRIVATE_KEY", default="").replace("\\n", "\n")
_SESTANTE_CLIENT_ID     = env.str("SOCIAL_SESTANTE_CLIENT_ID", default="")
_SESTANTE_CLIENT_SECRET = env.str("SOCIAL_SESTANTE_CLIENT_SECRET", default="")

# Senza "/" finale: allauth aggiunge "/.well-known/openid-configuration" e con la doppia
# barra authentik risponde 404 (errore 500 al clic su "Accedi con SSO").
_SESTANTE_SERVER_URL    = env.str(
    "SOCIAL_SESTANTE_SERVER_URL",
    default="https://auth.agescicampania.net/application/o/plancia/",
).rstrip("/")

# Un provider senza client id non va configurato: allauth mostrerebbe comunque il
# pulsante nella pagina di login, che poi fallirebbe. L'app parte anche senza credenziali.
SOCIALACCOUNT_PROVIDERS: dict = {}
if _GOOGLE_CLIENT_ID:
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "APP": {
            "client_id": _GOOGLE_CLIENT_ID,
            "secret": _GOOGLE_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "FETCH_USERINFO": True,
    }
if _MS_CLIENT_ID:
    SOCIALACCOUNT_PROVIDERS["microsoft"] = {
        "APP": {
            "client_id": _MS_CLIENT_ID,
            "secret": _MS_CLIENT_SECRET,
        },
        "TENANT": "common",
        "SCOPE": ["User.Read"],
    }
if _APPLE_CLIENT_ID:
    SOCIALACCOUNT_PROVIDERS["apple"] = {
        "APP": {
            "client_id": _APPLE_CLIENT_ID,
            "secret": _APPLE_KEY_ID,       # KEY_ID — usato come `kid` nell'header JWT
            "key": _APPLE_TEAM_ID,         # TEAM_ID — usato come `iss` nel JWT
            "settings": {
                "certificate_key": _APPLE_PRIVATE_KEY,  # chiave privata PEM
            },
        },
    }
# SSO AGESCI Campania (Sestante). Callback: /accounts/oidc/sestante/login/callback/
# Vedi docs/guide/sso_sestante.md. Formato APPS, non SERVERS: nella conversione da SERVERS
# allauth tiene solo server_url e scarta SCOPE (si userebbero sempre gli scope predefiniti,
# senza `avatar`). C'è un test sugli scope effettivi.
SESTANTE_APP = {
    "provider_id": "sestante",
    "name": "SSO AGESCI Campania",
    "client_id": _SESTANTE_CLIENT_ID,
    "secret":    _SESTANTE_CLIENT_SECRET,
    "settings": {
        "server_url": _SESTANTE_SERVER_URL,
        # avatar: immagine del profilo (claim `picture` in userinfo, apps.accounts.avatar)
        "scope": ["openid", "profile", "email", "avatar"],
    },
}
if _SESTANTE_CLIENT_ID:
    SOCIALACCOUNT_PROVIDERS["openid_connect"] = {"APPS": [SESTANTE_APP]}

SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.PlanciaSocialAccountAdapter"
ACCOUNT_ADAPTER = "apps.accounts.adapters.PlanciaAccountAdapter"

# --- MFA (allauth.mfa) -------------------------------------------------------
MFA_ADAPTER = "apps.accounts.adapters.PlanciaMFAAdapter"
MFA_TOTP_ISSUER = "Plancia AGESCI Campania"
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes", "webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_PASSKEY_SIGNUP_ENABLED = False

# --- allauth headless -------------------------------------------------------
# HEADLESS_ONLY: nessuna pagina allauth di Django; restano /_allauth/ (browser per la SPA,
# app per l'app mobile) e le callback dei provider social/SSO sotto /accounts/.
# TOKEN_STRATEGY sessions: il client mobile invia il session key nell'header X-Session-Token.
HEADLESS_ONLY = True
HEADLESS_TOKEN_STRATEGY = "allauth.headless.tokens.strategies.sessions.SessionTokenStrategy"
HEADLESS_CLIENTS = ("browser", "app")
# Pagine della SPA (frontend/src/router) a cui puntano i link delle email di allauth e i
# redirect dei provider social/SSO (con HEADLESS_ONLY sono obbligatori).
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": "/email/verifica/{key}",
    "account_reset_password": "/accesso/password",
    "account_reset_password_from_key": "/password/reset/{key}",
    "account_signup": "/accesso",
    "socialaccount_login_error": "/accesso/ritorno",
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N / TZ --------------------------------------------------------------
LANGUAGE_CODE = "it"
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True

# --- Static / media ---------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"  # transitorio: i file definitivi vanno su Drive

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Celery -----------------------------------------------------------------
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BEAT_SCHEDULE = {
    # Ultima release su GitHub per la pagina Impostazioni → Aggiornamenti (solo Admin).
    "controlla-ultima-release": {
        "task": "aggiornamenti.controlla_ultima_release",
        "schedule": crontab(hour=4, minute=17),
    },
}

# --- Aggiornamento del server dal web ----------------------------------------
# Cartella (bind mount dal repo sul server: /opt/plancia/aggiornamenti) in cui Django scrive
# richiesta.json e legge stato.json del runner sull'host. Vedi docs/api/aggiornamenti.md.
AGGIORNAMENTI_DIR = Path(env.str("AGGIORNAMENTI_DIR", default=str(BASE_DIR / "aggiornamenti")))
# Token GitHub read-only opzionale (alza il limite di 60 richieste/ora dell'API anonima).
GITHUB_TOKEN_RELEASES = env.str("GITHUB_TOKEN_RELEASES", default="")

# --- URL base (usato da notifications/service.py per i link di attivazione) --
BASE_URL = env.str("BASE_URL", default="http://localhost:8000")

# --- Notifiche errori agli amministratori -----------------------------------
# ADMIN_EMAILS: lista di indirizzi separati da virgola (es. "a@b.it,c@d.it").
# Se vuota, le notifiche di errore via email sono disabilitate.
_admin_emails = env.list("ADMIN_EMAILS", default=[])
ADMINS = [("Plancia Admin", e) for e in _admin_emails]
SERVER_EMAIL = env.str("SERVER_EMAIL", default="plancia@agescicampania.net")
EMAIL_SUBJECT_PREFIX = "[Plancia] "

# Vista CSRF failure: pagina statica (JSON sui percorsi API), vedi config/error_views.py.
CSRF_FAILURE_VIEW = "config.error_views.csrf_failure"

# --- Email ------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="plancia@agescicampania.net")

# Mailer (Django 6.1): tutti passano da PlanciaEmailBackend, che rispetta
# Impostazioni.email_mode e instrada "standard" e "massivo" ai backend configurati.
# "default" è usato da allauth, mail_admins e da chi non indica `using`.
_MAILER_PLANCIA = "apps.siteconfig.email_backends.PlanciaEmailBackend"
MAILERS = {
    "default": {"BACKEND": _MAILER_PLANCIA},
    "standard": {"BACKEND": _MAILER_PLANCIA, "OPTIONS": {"tipo": "standard"}},
    "massivo": {"BACKEND": _MAILER_PLANCIA, "OPTIONS": {"tipo": "massivo"}},
}
# SMTP di riserva quando Impostazioni non ha host/credenziali (prima configurazione).
SMTP_RISERVA = {
    "host": env.str("EMAIL_HOST", default=""),
    "port": env.int("EMAIL_PORT", default=587),
    "username": env.str("EMAIL_HOST_USER", default=""),
    "password": env.str("EMAIL_HOST_PASSWORD", default=""),
}

# Cartella dove la modalita' "simulato" scrive i messaggi (un file per invio).
LOG_DIR = BASE_DIR / "logs"

# --- Mailpit (debug email in produzione) ------------------------------------
# URL interno raggiungibile da Django per il proxy web UI e per l'SMTP.
# In nginx-docker mode: mailpit e web sono nella stessa rete compose.
# In nginx-host/apache-host mode: impostare http://localhost:8025 (porta esposta su loopback).
MAILPIT_INTERNAL_URL = env.str("MAILPIT_INTERNAL_URL", default="http://mailpit:8025")
FLOWER_INTERNAL_URL = env.str("FLOWER_INTERNAL_URL", default="http://flower:5555")
MAILPIT_SMTP_HOST = env.str("MAILPIT_SMTP_HOST", default="mailpit")
MAILPIT_SMTP_PORT = env.int("MAILPIT_SMTP_PORT", default=1025)
# Servizi facoltativi attivi: i profili compose in COMPOSE_PROFILES (.env, letto anche dal
# container web). Senza il profilo la SPA non mostra la voce di menu né il pulsante.
_PROFILI_COMPOSE = {p.strip() for p in env.list("COMPOSE_PROFILES", default=[]) if p.strip()}
FLOWER_ATTIVO = "flower" in _PROFILI_COMPOSE
MAILPIT_ATTIVO = "mailpit" in _PROFILI_COMPOSE

# --- Anymail (provider transazionale) ---------------------------------------
# I valori vengono sovrascritti a runtime dalla PlanciaEmailBackend che legge da DB.
# Le variabili d'ambiente qui sotto servono come fallback in ambienti senza DB
# o per il secret webhook (leggi docs/guide/email_provider.md).
ANYMAIL: dict = {}
EMAIL_SIMULATO_DIR = LOG_DIR / "email"
EMAIL_SIMULATO_DIR.mkdir(parents=True, exist_ok=True)

# --- Logging ----------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "std"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "plancia.log"),
            "maxBytes": 5_000_000,
            "backupCount": 5,
            "formatter": "std",
        },
        # Invia email agli ADMINS per ogni errore 500 (livello ERROR su django.request).
        # fail_silently=True evita eccezioni secondarie se l'email non è configurata.
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "include_html": True,
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["mail_admins"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}
# NB: il flag "debug_diagnostico" di Impostazioni alza a runtime il livello di logging
# per gli admin; NON ribalta settings.DEBUG (vedi docs sez. 15).

# --- Impersonazione (django-hijack) -----------------------------------------
# Autorizzazione per rango: Admin/Segreteria possono impersonare ruoli con
# rango <= al proprio (la Segreteria non puo' impersonare un Admin). Vedi docs sez. 2.
# Usata da apps.accounts.services.avvia_impersonazione (API); gli URL di hijack non sono montati.
HIJACK_PERMISSION_CHECK = "apps.accounts.roles.can_hijack"

# --- Google Drive OAuth -----------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = env.str("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env.str("GOOGLE_OAUTH_CLIENT_SECRET", default="")
GOOGLE_OAUTH_REDIRECT_URI = env.str(
    "GOOGLE_OAUTH_REDIRECT_URI",
    default="http://localhost:8000/drive/oauth/callback/",
)

# --- Gmail SMTP OAuth (scope https://mail.google.com/) ----------------------
GOOGLE_GMAIL_SMTP_REDIRECT_URI = env.str(
    "GOOGLE_GMAIL_SMTP_REDIRECT_URI",
    default="http://localhost:8000/impostazioni/gmail-smtp/oauth/callback/",
)

# --- Export riassuntivo diari -----------------------------------------------
# Soglia diari oltre la quale l'export xlsx/ods avviene in modo asincrono (via email).
EXPORT_DIARI_SOGLIA_ASYNC: int = 50
# Il CSV è sempre generato in modo sincrono (piccolo e veloce).
EXPORT_DIARI_CSV_SEMPRE_SYNC: bool = True

# --- CORS (django-cors-headers) ---------------------------------------------
# Solo per l'app mobile: la SPA è same-origin e non ne ha bisogno. L'app usa allauth
# headless in modalità *app* (/_allauth/app/) e l'API con X-Session-Token, mai i cookie:
# niente credenziali cross-origin, e CORS solo su quei percorsi.
# CORS_ALLOWED_ORIGINS nell'env (vuota = nessuna origine esterna; le app native non la usano).
CORS_ALLOWED_ORIGINS: list[str] = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_URLS_REGEX = r"^/(api/v1|_allauth/app)/"
CORS_ALLOW_CREDENTIALS = False
# Header custom necessario per l'auth app-client di allauth headless.
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-session-token",
]
