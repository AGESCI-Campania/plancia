# config/settings/base.py
"""Impostazioni condivise. Override in dev.py / prod.py."""
import subprocess
import tomllib
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Versione e commit (usati nel footer e nel template impostazioni) -------
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
# Carica un eventuale file .env (dev: .env.dev ; prod: .env.prod) se presente.
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
    "agesci_theme",
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
    "pwa",
    "tinymce",
    "hijack",
    "hijack.contrib.admin",
    "django_bootstrap_icons",
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
    "apps.api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
                "agesci_theme.context_processors.agesci_theme",
                "apps.siteconfig.context_processors.impostazioni",
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

# allauth (rifinire secondo docs sez. 12)
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_FORMS = {
    "login": "apps.accounts.forms.PlanciaLoginForm",
    "signup": "apps.accounts.forms.PlanciaSignupForm",
    "reset_password": "apps.accounts.forms.PlanciaResetPasswordForm",
    "change_password": "apps.accounts.forms.PlanciaChangePasswordForm",
    "set_password": "apps.accounts.forms.PlanciaSetPasswordForm",
    "add_email": "apps.accounts.forms.PlanciaAddEmailForm",
}
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

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": _GOOGLE_CLIENT_ID,
            "secret": _GOOGLE_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "FETCH_USERINFO": True,
    },
    "microsoft": {
        "APP": {
            "client_id": _MS_CLIENT_ID,
            "secret": _MS_CLIENT_SECRET,
        },
        "TENANT": "common",
        "SCOPE": ["User.Read"],
    },
    "apple": {
        "APP": {
            "client_id": _APPLE_CLIENT_ID,
            "secret": _APPLE_KEY_ID,       # KEY_ID — usato come `kid` nell'header JWT
            "key": _APPLE_TEAM_ID,         # TEAM_ID — usato come `iss` nel JWT
            "settings": {
                "certificate_key": _APPLE_PRIVATE_KEY,  # chiave privata PEM
            },
        },
    },
    "openid_connect": {
        "SERVERS": [
            {
                "id": "sestante",
                "name": "SSO AGESCI Campania",
                "server_url": "https://auth.agescicampania.org/application/o/plancia/",
                "APP": {
                    "client_id": _SESTANTE_CLIENT_ID,
                    "secret":    _SESTANTE_CLIENT_SECRET,
                },
                "SCOPE": ["openid", "profile", "email"],
            }
        ]
    },
}

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
# HEADLESS_ONLY=False: manteniamo l'UI web tradizionale affiancata all'API.
# TOKEN_STRATEGY sessions: il client mobile invia il session key nell'header X-Session-Token.
HEADLESS_ONLY = False
HEADLESS_TOKEN_STRATEGY = "allauth.headless.tokens.strategies.sessions.SessionTokenStrategy"
HEADLESS_CLIENTS = ("browser", "app")

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
STATICFILES_DIRS = [BASE_DIR / "static"]
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

# --- PWA (django-pwa) -------------------------------------------------------
PWA_APP_NAME = env.str("PWA_APP_NAME", default="Plancia")
PWA_APP_DESCRIPTION = "Gestione Guidoncini Verdi - AGESCI Campania"
PWA_APP_THEME_COLOR = "#5AA02C"  # verde GV (vedi palette docs)
PWA_APP_BACKGROUND_COLOR = "#ffffff"
PWA_APP_DISPLAY = "standalone"
PWA_APP_START_URL = "/"
PWA_APP_LANG = "it-IT"
PWA_APP_DIR = "ltr"
PWA_APP_DEBUG_MODE = False
# Service worker personalizzato (sostituisce il default vuoto di django-pwa)
PWA_SERVICE_WORKER_PATH = BASE_DIR / "static" / "js" / "plancia-sw.js"
PWA_APP_ICONS = [
    {"src": "/static/images/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/static/images/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png"},
]
PWA_APP_ICONS_APPLE = [
    {"src": "/static/images/icons/apple-touch-icon.png", "sizes": "180x180"},
]
PWA_APP_SPLASH_SCREEN = [
    # ---------- iPhone ----------
    # iPhone 5 / 5s / SE (1ª gen)
    {
        'src': '/static/images/icons/splash-640x1136.png',
        'media': '(device-width: 320px) and (device-height: 568px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPhone 6 / 7 / 8 / SE (2ª e 3ª gen)
    {
        'src': '/static/images/icons/splash-750x1334.png',
        'media': '(device-width: 375px) and (device-height: 667px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPhone 6+ / 7+ / 8+
    {
        'src': '/static/images/icons/splash-1242x2208.png',
        'media': '(device-width: 414px) and (device-height: 736px) and (-webkit-device-pixel-ratio: 3)'
    },
    # iPhone X / XS / 11 Pro / 12 mini / 13 mini
    {
        'src': '/static/images/icons/splash-1125x2436.png',
        'media': '(device-width: 375px) and (device-height: 812px) and (-webkit-device-pixel-ratio: 3)'
    },
    # iPhone XR / 11
    {
        'src': '/static/images/icons/splash-828x1792.png',
        'media': '(device-width: 414px) and (device-height: 896px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPhone XS Max / 11 Pro Max
    {
        'src': '/static/images/icons/splash-1242x2688.png',
        'media': '(device-width: 414px) and (device-height: 896px) and (-webkit-device-pixel-ratio: 3)'
    },
    # iPhone 12 / 12 Pro / 13 / 13 Pro / 14
    {
        'src': '/static/images/icons/splash-1170x2532.png',
        'media': '(device-width: 390px) and (device-height: 844px) and (-webkit-device-pixel-ratio: 3)'
    },
    # iPhone 12 Pro Max / 13 Pro Max / 14 Plus
    {
        'src': '/static/images/icons/splash-1284x2778.png',
        'media': '(device-width: 428px) and (device-height: 926px) and (-webkit-device-pixel-ratio: 3)'
    },
    # iPhone 14 Pro / 15 / 15 Pro / 16
    {
        'src': '/static/images/icons/splash-1179x2556.png',
        'media': '(device-width: 393px) and (device-height: 852px) and (-webkit-device-pixel-ratio: 3)'
    },
    # iPhone 14 Pro Max / 15 Plus / 15 Pro Max / 16 Plus
    {
        'src': '/static/images/icons/splash-1290x2796.png',
        'media': '(device-width: 430px) and (device-height: 932px) and (-webkit-device-pixel-ratio: 3)'
    },
    # iPhone 16 Pro
    {
        'src': '/static/images/icons/splash-1206x2622.png',
        'media': '(device-width: 402px) and (device-height: 874px) and (-webkit-device-pixel-ratio: 3)'
    },
    # iPhone 16 Pro Max
    {
        'src': '/static/images/icons/splash-1320x2868.png',
        'media': '(device-width: 440px) and (device-height: 956px) and (-webkit-device-pixel-ratio: 3)'
    },

    # ---------- iPad ----------
    # iPad 9.7" / iPad mini 5 e precedenti
    {
        'src': '/static/images/icons/splash-1536x2048.png',
        'media': '(device-width: 768px) and (device-height: 1024px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPad 10.2" (7ª-9ª gen)
    {
        'src': '/static/images/icons/splash-1620x2160.png',
        'media': '(device-width: 810px) and (device-height: 1080px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPad mini 6 / 7
    {
        'src': '/static/images/icons/splash-1488x2266.png',
        'media': '(device-width: 744px) and (device-height: 1133px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPad Air 10.5" / iPad Pro 10.5"
    {
        'src': '/static/images/icons/splash-1668x2224.png',
        'media': '(device-width: 834px) and (device-height: 1112px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPad 10.9" (10ª gen) / iPad Air 4 e 5 / iPad Air 11" (M2)
    {
        'src': '/static/images/icons/splash-1640x2360.png',
        'media': '(device-width: 820px) and (device-height: 1180px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPad Pro 11"
    {
        'src': '/static/images/icons/splash-1668x2388.png',
        'media': '(device-width: 834px) and (device-height: 1194px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPad Pro 12.9"
    {
        'src': '/static/images/icons/splash-2048x2732.png',
        'media': '(device-width: 1024px) and (device-height: 1366px) and (-webkit-device-pixel-ratio: 2)'
    },
    # iPad Pro 13" (M4)
    {
        'src': '/static/images/icons/splash-2064x2752.png',
        'media': '(device-width: 1032px) and (device-height: 1376px) and (-webkit-device-pixel-ratio: 2)'
    },
]

PWA_APP_SHORTCUTS = [
    {
        "name": "Diari",
        "short_name": "Diari",
        "description": "Apri la lista dei diari di bordo",
        "url": "/diari/",
        "icons": [{"src": "/static/images/icons/icon-192x192.png", "sizes": "192x192"}],
    },
    {
        "name": "Valutazioni",
        "short_name": "Valutazioni",
        "description": "Apri la lista delle valutazioni",
        "url": "/valutazioni/",
        "icons": [{"src": "/static/images/icons/icon-192x192.png", "sizes": "192x192"}],
    },
    {
        "name": "Helpdesk",
        "short_name": "Helpdesk",
        "description": "Apri i ticket di supporto",
        "url": "/helpdesk/",
        "icons": [{"src": "/static/images/icons/icon-192x192.png", "sizes": "192x192"}],
    },
]

# --- Bootstrap Icons (django-bootstrap-icons) --------------------------------
# Versione CDN allineata a quella usata nei template; cache su disco in .icon_cache/
BS_ICONS_BASE_URL = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/"
BS_ICONS_CACHE = BASE_DIR / ".icon_cache"

# --- Google Drive (storage_drive) ------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = env.str("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env.str("GOOGLE_OAUTH_CLIENT_SECRET", default="")

# --- URL base (usato da notifications/service.py per i link di attivazione) --
BASE_URL = env.str("BASE_URL", default="http://localhost:8000")

# --- Notifiche errori agli amministratori -----------------------------------
# ADMIN_EMAILS: lista di indirizzi separati da virgola (es. "a@b.it,c@d.it").
# Se vuota, le notifiche di errore via email sono disabilitate.
_admin_emails = env.list("ADMIN_EMAILS", default=[])
ADMINS = [("Plancia Admin", e) for e in _admin_emails]
SERVER_EMAIL = env.str("SERVER_EMAIL", default="plancia@agescicampania.org")
EMAIL_SUBJECT_PREFIX = "[Plancia] "

# Vista CSRF failure: mostra un template brandizzato invece della pagina Django.
CSRF_FAILURE_VIEW = "config.error_views.csrf_failure"

# --- Email ------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="plancia@agescicampania.org")

# Il tema usa alert-{{ message.tags }}: "error" non è una classe Bootstrap valida,
# serve "danger". MESSAGE_TAGS mappa i livelli Django ai tag Bootstrap corretti.
# noqa: E402 — import posizionato qui per leggibilità vicino all'uso
MESSAGE_TAGS = {40: "danger"}  # 40 = messages.ERROR

# Backend custom: rispetta Impostazioni.email_mode (reale / simulato / simulato_piu_invio).
# In dev (vedi dev.py) si usa il backend console.
EMAIL_BACKEND = "apps.siteconfig.email_backends.PlanciaEmailBackend"
EMAIL_HOST = env.str("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

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

# --- Anymail (provider transazionale) ---------------------------------------
# I valori vengono sovrascritti a runtime dalla PlanciaEmailBackend che legge da DB.
# Le variabili d'ambiente qui sotto servono come fallback in ambienti senza DB
# o per il secret webhook (leggi docs/guide/email_provider.md).
ANYMAIL: dict = {}
EMAIL_FILE_PATH = LOG_DIR / "email"
(EMAIL_FILE_PATH).mkdir(parents=True, exist_ok=True)

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

# --- AGESCI Theme -----------------------------------------------------------
AGESCI_THEME_BRANCA = "eg"
AGESCI_THEME_NOME = "AGESCI Campania"

# --- TinyMCE ----------------------------------------------------------------
TINYMCE_DEFAULT_CONFIG = {
    "plugins": "link code lists image",
    "toolbar": "undo redo | bold italic | bullist numlist | link image | code",
    "menubar": False,
    "height": 400,
    "link_assume_external_targets": True,
    "default_link_target": "_blank",
    "link_title": False,
    "images_upload_url": "/impostazioni/mail/upload-immagine/",
    "automatic_uploads": True,
    "file_picker_types": "image",
    "images_reuse_filename": False,
}

# --- Impersonazione (django-hijack) -----------------------------------------
# Autorizzazione per rango: Admin/Segreteria possono impersonare ruoli con
# rango <= al proprio (la Segreteria non puo' impersonare un Admin). Vedi docs sez. 2.
HIJACK_PERMISSION_CHECK = "apps.accounts.roles.can_hijack"
HIJACK_LOGIN_REDIRECT_URL = "/"
HIJACK_LOGOUT_REDIRECT_URL = "/"

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
# Origini autorizzate per l'API REST (es. app mobile React Native).
# In produzione impostare CORS_ALLOWED_ORIGINS nell'env.
CORS_ALLOWED_ORIGINS: list[str] = env.list("CORS_ALLOWED_ORIGINS", default=[])
# Necessario perché il client mobile invia i cookie di sessione (o X-Session-Token).
CORS_ALLOW_CREDENTIALS = True
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
