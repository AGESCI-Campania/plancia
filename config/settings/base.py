# config/settings/base.py
"""Impostazioni condivise. Override in dev.py / prod.py."""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
# Carica un eventuale file .env (dev: .env.dev ; prod: .env.prod) se presente.
_env_file = env.str("DJANGO_ENV_FILE", default=str(BASE_DIR / ".env.dev"))
if Path(_env_file).exists():
    environ.Env.read_env(_env_file)

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
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
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.microsoft",
    "allauth.socialaccount.providers.apple",
    "guardian",
    "axes",
    "pwa",
    "tinymce",
    "hijack",
    "hijack.contrib.admin",
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
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
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
            "secret": _APPLE_PRIVATE_KEY,
            "key": _APPLE_KEY_ID,
            "certificate_key": _APPLE_PRIVATE_KEY,
        },
        "TEAM_ID": _APPLE_TEAM_ID,
    },
}

SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.PlanciaSocialAccountAdapter"

# --- MFA (allauth.mfa) -------------------------------------------------------
MFA_ADAPTER = "apps.accounts.adapters.PlanciaMFAAdapter"
MFA_TOTP_ISSUER = "Plancia AGESCI Campania"

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
PWA_APP_NAME = "Plancia"
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
# Icone: aggiungere /static/images/icons/icon-*.png (asset grafici separati)
PWA_APP_ICONS = []
PWA_APP_ICONS_APPLE = []
PWA_APP_SPLASH_SCREEN = []

# --- Google Drive (storage_drive) ------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = env.str("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env.str("GOOGLE_OAUTH_CLIENT_SECRET", default="")

# --- URL base (usato da notifications/service.py per i link di attivazione) --
BASE_URL = env.str("BASE_URL", default="http://localhost:8000")

# --- Email ------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="plancia@agescicampania.org")

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
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
}
# NB: il flag "debug_diagnostico" di Impostazioni alza a runtime il livello di logging
# per gli admin; NON ribalta settings.DEBUG (vedi docs sez. 15).

# --- AGESCI Theme -----------------------------------------------------------
AGESCI_THEME_BRANCA = "eg"
AGESCI_THEME_NOME = "AGESCI Campania"

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
