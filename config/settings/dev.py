# config/settings/dev.py
from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE, STORAGES

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Email via Mailpit (SMTP fake locale — UI: http://localhost:8025)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "localhost"
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
# Mailpit proxy (/mailadmin/) — in dev Mailpit gira su localhost
MAILPIT_INTERNAL_URL = "http://localhost:8025"
MAILPIT_SMTP_HOST = "localhost"
MAILPIT_SMTP_PORT = 1025

# In dev non bloccare il login con la verifica email
ACCOUNT_EMAIL_VERIFICATION = "none"

# Celery eager: i task girano in-process (niente worker necessario per provare)
CELERY_TASK_ALWAYS_EAGER = True

# django-debug-toolbar (opzionale)
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS = INSTALLED_APPS + ["debug_toolbar"]
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]
    INTERNAL_IPS = ["127.0.0.1"]
except ImportError:
    pass

# In dev disattiviamo il blocco di axes per comodità
AXES_ENABLED = False

# In dev accetta richieste CORS da qualsiasi origine (es. emulatore mobile locale).
CORS_ALLOW_ALL_ORIGINS = True

# Bypass TOTP per test/screenshot: qualunque utente con TOTP configurato
# può usare questo codice fisso anziché il codice reale generato dall'app.
# NON abilitare in produzione.
MFA_TOTP_INSECURE_BYPASS_CODE = "000000"

# In dev (e nei test) non serve il manifest generato da collectstatic
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
