# config/settings/prod.py
from .base import *  # noqa: F401,F403
from .base import AUTHENTICATION_BACKENDS, env

# DEBUG REALE governato dall'ambiente: per attivarlo, imposta DJANGO_DEBUG=true in
# .env.prod e RIAVVIA/REDEPLOY i container (si legge all'avvio). Attivarlo in
# produzione e' un rischio di sicurezza: usarlo solo per diagnosi puntuali.
DEBUG = env.bool("DJANGO_DEBUG", default=False)

# Dietro reverse proxy (nginx/apache, dockerizzato o esistente)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Hardening (vedi docs sez. 12)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # cookie di sessione eliminato alla chiusura del browser
SESSION_COOKIE_AGE = 4 * 60 * 60  # 4 ore — timeout assoluto anche con browser aperto
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Content-Security-Policy (Django 6 nativo) - da rifinire con gli host reali
SECURE_CSP = {
    "default-src": ["'self'"],
    "img-src": ["'self'", "data:", "https:"],
    "style-src": ["'self'", "'unsafe-inline'"],
}

# Cache Redis condivisa tra tutti i worker gunicorn (evita la LocMemCache per-processo)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env.str("REDIS_CACHE_URL", "redis://redis:6379/2"),
        "KEY_PREFIX": "plancia",
        "TIMEOUT": 300,
    }
}

# axes per primo in produzione
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", *AUTHENTICATION_BACKENDS]

# Email: gestita da PlanciaEmailBackend (base.py).
# Provider e credenziali configurabili da Impostazioni admin.
# SMTP fallback per ambienti senza DB o prima configurazione:
EMAIL_HOST = env.str("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
