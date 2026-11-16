# config/settings/prod.py
from .base import *  # noqa: F401,F403
from .base import AUTHENTICATION_BACKENDS, env

# DEBUG REALE governato dall'ambiente: per attivarlo, imposta DJANGO_DEBUG=true in
# .env e RICREA i container con docker compose up -d (si legge all'avvio). Attivarlo in
# produzione e' un rischio di sicurezza: usarlo solo per diagnosi puntuali.
DEBUG = env.bool("DJANGO_DEBUG", default=False)

# Dietro reverse proxy: Caddy (agesci-campania-web-frontend) → nginx interno, solo HTTP
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Hardening (vedi docs sez. 12)
# Il redirect HTTP→HTTPS lo fa Caddy; tenerlo attivo funziona grazie a SECURE_PROXY_SSL_HEADER
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

# Dietro due proxy l'IP del client va letto da X-Forwarded-For, non da REMOTE_ADDR
AXES_CLIENT_IP_CALLABLE = "apps.siteconfig.axes_helpers.ip_client_dietro_proxy"

# axes per primo in produzione
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", *AUTHENTICATION_BACKENDS]

# Email: MAILERS e SMTP_RISERVA in base.py; provider e credenziali da Impostazioni.
